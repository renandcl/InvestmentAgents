"""Managed-runtime failure, cancellation, worker and crash-gap contracts."""

import asyncio
import json
import multiprocessing
import os
import sqlite3
import subprocess
import threading
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from test_run_store import publish

from runtime.artifacts import export_final
from runtime.context import MemoryMode, RunConfig
from runtime.errors import RunExecutionError, RunNotWritable
from runtime.lifecycle import create_run
from runtime.memory import NullMemory
from runtime.resources import ResourceRegistry
from runtime.store import RunStore


class ReportingAgent:
    def __init__(self, *, runtime):
        self.runtime = runtime

    async def invoke_async(self, message):
        publish(self.runtime.store, "investment_manager", message)
        return SimpleNamespace(stop_reason="end_turn")


def crash_gap_worker(root, queue, ready, release):
    runtime = create_run(RunConfig("AAPL", "2026-01-01", output_root=Path(root)))
    queue.put(runtime.context)

    def interrupted_export(context, snapshot):
        result = export_final(context, snapshot)
        ready.set()
        release.wait(timeout=60)
        return result

    with patch("runtime.lifecycle.export_final", interrupted_export):
        asyncio.run(
            runtime.execute(ReportingAgent, "decision", "investment_manager_report")
        )


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def runtime(self, **kwargs):
        return create_run(
            RunConfig("AAPL", "2026-01-01", output_root=Path(self.tmp.name), **kwargs)
        )

    async def test_repeat_and_interleaved_runs_export_independent_artifacts(self):
        a, b = self.runtime(), self.runtime()
        env, cwd = dict(os.environ), Path.cwd()
        barrier = asyncio.Barrier(2)

        class Paired(ReportingAgent):
            async def invoke_async(self, message):
                await barrier.wait()
                return await super().invoke_async(message)

        ra, rb = await asyncio.gather(
            a.execute(Paired, "sentinel-A", "investment_manager_report"),
            b.execute(Paired, "sentinel-B", "investment_manager_report"),
        )
        self.assertNotEqual(ra.run_id, rb.run_id)
        self.assertNotIn("sentinel-B", ra.report_path.read_text(encoding="utf-8"))
        self.assertNotIn("sentinel-A", rb.report_path.read_text(encoding="utf-8"))
        self.assertEqual(
            json.loads(ra.state_path.read_text(encoding="utf-8"))["status"], "SUCCEEDED"
        )
        self.assertEqual(os.environ, env)
        self.assertEqual(Path.cwd(), cwd)
        with self.assertRaises(RunNotWritable):
            await a.execute(Paired, "again", "investment_manager_report")

    async def test_partial_construction_cleanup_reverse_and_other_run_usable(self):
        a, b = self.runtime(), self.runtime()
        calls = []

        def failing_factory(*, runtime):
            runtime.resources.register(lambda: calls.append("first"))
            runtime.resources.register(lambda: calls.append("partial-second"))
            raise RuntimeError("credential-must-not-leak")

        with self.assertRaises(RunExecutionError) as raised:
            await a.execute(failing_factory, "decision", "investment_manager_report")
        self.assertEqual(calls, ["partial-second", "first"])
        self.assertEqual(raised.exception.run_id, a.context.run_id)
        self.assertEqual(a.store.inspect()["status"], "FAILED")
        self.assertNotIn(
            "credential-must-not-leak", a.context.path("manifest.json").read_text()
        )
        self.assertEqual(
            (await b.execute(ReportingAgent, "ok", "investment_manager_report")).status,
            "SUCCEEDED",
        )

    async def test_root_absence_and_export_failure_cannot_commit_success(self):
        class NoReport(ReportingAgent):
            async def invoke_async(self, message):
                return SimpleNamespace(stop_reason="end_turn")

        a, b = self.runtime(), self.runtime()
        with self.assertRaises(RunExecutionError):
            await a.execute(NoReport, "decision", "investment_manager_report")
        with patch("runtime.lifecycle.export_final", side_effect=OSError("secret")):
            with self.assertRaises(RunExecutionError):
                await b.execute(ReportingAgent, "decision", "investment_manager_report")
        for runtime in (a, b):
            self.assertEqual(runtime.store.inspect()["status"], "FAILED")
            self.assertEqual(runtime.store.inspect()["artifacts"], [])

    async def test_cancel_invocation_closes_owned_resources_and_propagates(self):
        runtime = self.runtime()
        ready, closed = asyncio.Event(), threading.Event()

        class Waiting(ReportingAgent):
            async def invoke_async(self, message):
                self.runtime.resources.register(closed.set)
                ready.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(
            runtime.execute(Waiting, "decision", "investment_manager_report")
        )
        await ready.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError) as raised:
            await task
        self.assertEqual(raised.exception.run_id, runtime.context.run_id)
        self.assertTrue(closed.is_set())
        self.assertEqual(runtime.store.inspect()["status"], "CANCELLED")

    async def test_cancel_during_cleanup_waits_for_owned_callback(self):
        runtime = self.runtime()
        cleanup_started, release = asyncio.Event(), asyncio.Event()

        async def cleanup():
            cleanup_started.set()
            await release.wait()

        runtime.resources.register(cleanup)
        task = asyncio.create_task(
            runtime.execute(ReportingAgent, "decision", "investment_manager_report")
        )
        await cleanup_started.wait()
        task.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(runtime.store.inspect()["status"], "CANCELLED")
        self.assertTrue(runtime.resources._closed)

    async def test_cleanup_failure_does_not_skip_callbacks_or_claim_success(self):
        runtime = self.runtime()
        calls = []
        runtime.resources.register(lambda: calls.append("first"))

        def fail():
            calls.append("second")
            raise RuntimeError("secret")

        runtime.resources.register(fail)
        with self.assertRaises(RunExecutionError):
            await runtime.execute(
                ReportingAgent, "decision", "investment_manager_report"
            )
        self.assertEqual(calls, ["second", "first"])
        self.assertEqual(runtime.store.inspect()["status"], "FAILED")
        self.assertTrue(runtime.store.inspect()["cleanup_errors"])
        await runtime.resources.close()
        self.assertEqual(calls, ["second", "first"])

    async def test_deadline_records_timeout_and_attempts_remaining_cleanup(self):
        registry = ResourceRegistry(timeout=0.05)
        called, release = threading.Event(), threading.Event()
        registry.register(called.set)
        registry.register(release.wait)
        try:
            errors = await registry.close()
            self.assertTrue(called.is_set())
            self.assertIn("CleanupTimeout", [e.category for e in errors])
        finally:
            release.set()

    async def test_manifest_failure_after_commit_is_only_a_warning(self):
        runtime = self.runtime()
        from runtime.artifacts import refresh_manifest

        def refresh(store):
            if store.inspect()["status"] == "SUCCEEDED":
                raise OSError("failure")
            return refresh_manifest(store)

        with patch("runtime.lifecycle.refresh_manifest", side_effect=refresh):
            result = await runtime.execute(
                ReportingAgent, "decision", "investment_manager_report"
            )
        self.assertEqual(runtime.store.inspect()["status"], "SUCCEEDED")
        self.assertTrue(result.warnings)
        self.assertEqual(
            json.loads(runtime.context.path("manifest.json").read_text())["status"],
            "RUNNING",
        )

    async def test_off_memory_never_imports_or_starts_vendor(self):
        runtime = self.runtime()

        class WithMemory(ReportingAgent):
            async def invoke_async(self, message):
                memory = self.runtime.memory_for("trader")
                assert isinstance(memory, NullMemory)
                assert memory.search_memories("query", "AAPL") == {"results": []}
                memory.add_memory("memory", "AAPL")
                return await super().invoke_async(message)

        with patch(
            "runtime.memory.subprocess.Popen",
            side_effect=AssertionError("Must not start a worker"),
        ):
            await runtime.execute(WithMemory, "decision", "investment_manager_report")
        self.assertFalse(runtime.context.path("memory").exists())

    async def test_memory_workers_use_private_vendor_vector_history_and_filters(self):
        stub = Path(self.tmp.name) / "vendor-stub"
        package = stub / "mem0"
        package.mkdir(parents=True)
        # This fake runs in actual child processes and persists import/config evidence.
        package.joinpath("__init__.py").write_text(
            "import os,json,pathlib\n"
            "vendor=pathlib.Path(os.environ['MEM0_DIR']);vendor.mkdir(parents=True,exist_ok=True)\n"
            "(vendor/'import.json').write_text(json.dumps(dict(run=os.environ['INVESTMENT_RUN_ID'],telemetry=os.environ['MEM0_TELEMETRY'])))\n"
            "class Memory:\n"
            " @classmethod\n"
            " def from_config(cls,c):\n"
            "  (vendor/'config.json').write_text(json.dumps(c));m=cls();m.rows=[];return m\n"
            " def add(self,text,**scope):\n"
            "  self.rows.append(dict(memory=text,**scope));return {}\n"
            " def search(self,query,*,filters,top_k):\n"
            "  assert set(filters)=={'user_id','agent_id'};return {'results':[r for r in self.rows if all(r[k]==v for k,v in filters.items())][:top_k]}\n"
            " def get_all(self,*,filters):\n"
            "  return self.search('',filters=filters,top_k=100)\n",
            encoding="utf-8",
        )
        a, b = self.runtime(memory_mode=MemoryMode.RUN_ONLY), self.runtime(
            memory_mode=MemoryMode.RUN_ONLY
        )

        class MemoryAgent(ReportingAgent):
            async def invoke_async(self, message):
                memory = self.runtime.memory_for("trader")
                self.before = memory.get_memories()
                assert self.before == {"results": []}
                memory.add_memory(message, "AAPL")
                result = memory.search_memories("query", "AAPL")
                assert [r["memory"] for r in result["results"]] == [message]
                assert result["results"][0]["user_id"] == self.runtime.context.run_id
                return await super().invoke_async(message)

        with patch.dict(os.environ, {"PYTHONPATH": str(stub)}):
            environment = dict(os.environ)
            await asyncio.gather(
                a.execute(MemoryAgent, "A", "investment_manager_report"),
                b.execute(MemoryAgent, "B", "investment_manager_report"),
            )
            self.assertEqual(environment, dict(os.environ))
        for runtime in (a, b):
            memory = runtime._memories["trader"]
            self.assertIsNotNone(memory.process.poll())
            config = json.loads((memory.root / "vendor" / "config.json").read_text())
            self.assertEqual(
                config["history_db_path"], str(memory.root / "history.sqlite3")
            )
            self.assertEqual(
                config["vector_store"]["config"]["path"], str(memory.root / "chroma")
            )
            self.assertEqual(
                json.loads((memory.root / "vendor" / "import.json").read_text())[
                    "telemetry"
                ],
                "false",
            )

    async def test_real_mem0_chroma_worker_retrieval_and_auxiliary_paths(self):
        runtimes = [self.runtime(memory_mode=MemoryMode.RUN_ONLY) for _ in range(2)]
        environment = dict(os.environ)
        real_popen = subprocess.Popen

        def offline_worker(command, **kwargs):
            self.assertEqual(command[2:4], ["-m", "runtime.memory_worker"])
            command = (
                command[:2]
                + [
                    "-c",
                    "import runpy; runpy.run_path('tests/offline_memory_worker.py', run_name='__main__')",
                ]
                + command[4:]
            )
            return real_popen(command, **kwargs)

        class MemoryAgent(ReportingAgent):
            async def invoke_async(self, message):
                memory = self.runtime.memory_for("trader")
                assert memory.get_memories()["results"] == []
                memory.add_memory(message, "AAPL")
                for records in (
                    memory.search_memories("query", "AAPL", n_matches=1),
                    memory.get_memories(),
                ):
                    assert [row["memory"] for row in records["results"]] == [message]
                    assert all(
                        row["user_id"] == self.runtime.context.run_id
                        and row["agent_id"] == "trader"
                        for row in records["results"]
                    )
                return await super().invoke_async(message)

        with patch("runtime.memory.subprocess.Popen", side_effect=offline_worker):
            for runtime in runtimes:
                marker = "sentinel-" + runtime.context.run_id + "-trader"
                await runtime.execute(MemoryAgent, marker, "investment_manager_report")
        self.assertEqual(environment, dict(os.environ))
        for runtime in runtimes:
            memory = runtime._memories["trader"]
            self.assertIsNotNone(memory.process.poll())
            evidence = json.loads((memory.root / "vendor" / "probe.json").read_text())
            self.assertTrue(
                all(
                    Path(path).is_relative_to(memory.root) for path in evidence.values()
                )
            )
            self.assertEqual(evidence["chroma"], evidence["entities"])
            self.assertTrue((memory.root / "chroma" / "chroma.sqlite3").is_file())
            with closing(sqlite3.connect(memory.root / "history.sqlite3")) as db:
                rows = db.execute("SELECT new_memory FROM history").fetchall()
            self.assertIn(("sentinel-" + runtime.context.run_id + "-trader",), rows)
            other = next(r for r in runtimes if r is not runtime)
            self.assertFalse(any(other.context.run_id in str(row) for row in rows))


class CrashTests(unittest.TestCase):
    def test_kill_after_export_leaves_nonterminal_without_artifact_receipts(self):
        with TemporaryDirectory() as tmp:
            ctx = multiprocessing.get_context("spawn")
            queue, ready, release = ctx.Queue(), ctx.Event(), ctx.Event()
            process = ctx.Process(
                target=crash_gap_worker, args=(tmp, queue, ready, release)
            )
            process.start()
            try:
                context = queue.get(timeout=30)
                self.assertTrue(ready.wait(timeout=30))
                process.terminate()
                process.join(timeout=10)
                self.assertIsNotNone(process.exitcode)
                store = RunStore(context)
                self.assertEqual(store.inspect()["status"], "RUNNING")
                self.assertEqual(store.inspect()["artifacts"], [])
                self.assertTrue(context.path("report.md").is_file())
            finally:
                # A killed worker may leave an IPC event lock held. Never reuse it.
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=10)
                queue.close()


if __name__ == "__main__":
    unittest.main()
