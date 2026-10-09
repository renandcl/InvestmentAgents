"""Run-isolation acceptance at real SDK, application and process boundaries."""

import asyncio
import builtins
import importlib
import io
import json
import multiprocessing
import os
import runpy
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

import test_debates
from isolation_helpers import new_runtime
from strands import tool
from strands.models.model import Model

from agents.debates.state import RoundContext
from agents.hooks.lifecycle import AgentLifecycleHooks
from agents.hooks.specs import AGENT_SPECS
from runtime.agent import RunAgent
from runtime.cache import RunCache
from runtime.context import REPO_ROOT, RunConfig, resolve_models
from runtime.errors import (
    RunContextMismatch,
    RunExecutionError,
    StateConflict,
    UnsupportedExecutionMode,
)
from runtime.lifecycle import create_run
from runtime.memory import NullMemory
from runtime.store import RunStore


class WorkflowModel(Model):
    def __init__(self, agent_id, calls=None, entered=None, release=None, marker=None):
        self.agent_id, self.calls = agent_id, calls if calls is not None else []
        self.entered, self.release, self.marker = entered, release, marker

    def update_config(self, **kwargs):
        pass

    def get_config(self):
        return {"model_id": "offline"}

    async def structured_output(self, *args, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls.append(
            (self.agent_id, kwargs.get("invocation_state", {}).get("run_id"))
        )
        if self.entered:
            self.entered.set()
        if self.release:
            await self.release.wait()
        used = sum(
            "toolResult" in block
            for message in messages
            for block in message.get("content", [])
        )
        tools = tool_specs or []
        yield {"messageStart": {"role": "assistant"}}
        if used < len(tools):
            tool = tools[used]
            argument = next(iter(tool["inputSchema"]["json"]["properties"]))
            yield {
                "contentBlockStart": {
                    "contentBlockIndex": 0,
                    "start": {
                        "toolUse": {"toolUseId": f"tool-{used}", "name": tool["name"]}
                    },
                }
            }
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": 0,
                    "delta": {"toolUse": {"input": json.dumps({argument: "Analyze"})}},
                }
            }
            reason = "tool_use"
        else:
            text = (
                self.marker
                or f"{self.agent_id}: {kwargs.get('invocation_state', {}).get('run_id')}"
            )
            yield {
                "contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": text}}
            }
            reason = "end_turn"
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": reason}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 0},
            }
        }


def simple_agent(runtime, agent_id="market_analyst", **model_options):
    spec = AGENT_SPECS[agent_id]
    hook = AgentLifecycleHooks(
        spec, runtime=runtime, memory=NullMemory() if spec.memory else None
    )
    agent = RunAgent(
        runtime=runtime,
        agent_id=agent_id,
        model=WorkflowModel(agent_id, **model_options),
        hooks=[hook],
        session_manager=runtime.session_for(agent_id),
        callback_handler=None,
    )
    agent.lifecycle_hooks = hook
    return agent


def independent_worker(root, marker, barrier, queue):
    try:
        runtime = create_run(RunConfig("AAPL", "2025-08-01", output_root=Path(root)))
        environment, cwd = dict(os.environ), Path.cwd()

        class Factory:
            def __new__(cls, *, runtime):
                cache = RunCache.for_run(runtime, "finnhub-news-data-server")
                cache.write_json(cache.key("same", {}), {"data": [marker]})
                barrier.wait(timeout=20)
                return simple_agent(runtime, marker=marker)

        result = asyncio.run(
            runtime.execute(Factory, "Analyze", "market_analyst_report")
        )
        assert environment == dict(os.environ) and cwd == Path.cwd()
        queue.put(("ok", result.run_root, marker))
    except BaseException as error:
        queue.put(("error", type(error).__name__, marker))


def overlapping_manager_worker(context, barrier, queue):
    try:
        store = RunStore(context)
        barrier.wait(timeout=20)
        store.begin_debate(
            manager_id="research_manager",
            manager_invocation_id=uuid4().hex,
            operation_id=uuid4().hex,
        )
        queue.put("owner")
    except StateConflict:
        queue.put("conflict")
    except BaseException as error:
        queue.put(type(error).__name__)


class SDKIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = new_runtime(Path(self.tmp.name))

    async def test_one_agent_serializes_direct_stream_and_cancelled_waiter(self):
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        agent = simple_agent(
            self.runtime, entered=entered, release=release, calls=calls
        )
        first = asyncio.create_task(agent.invoke_async("first"))
        await entered.wait()
        first_messages = list(agent.messages)
        second_started = asyncio.Event()

        async def stream():
            second_started.set()
            return [event async for event in agent.stream_async("second")]

        second = asyncio.create_task(stream())
        await second_started.wait()
        self.assertEqual(agent.messages, first_messages)
        self.assertEqual(len(calls), 1)
        second.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await second
        release.set()
        await first
        await agent.invoke_async("third")
        self.assertEqual(len(calls), 2)
        self.assertIsNone(agent._active_invocation)
        self.assertFalse(self.runtime._invocations)
        sessions = list(self.runtime.context.path("sessions").rglob("*.json"))
        self.assertTrue(sessions)
        self.assertTrue(
            all(path.is_relative_to(self.runtime.context.run_root) for path in sessions)
        )

    async def test_different_agents_and_runs_progress_while_one_is_blocked(self):
        entered, release = asyncio.Event(), asyncio.Event()
        first = simple_agent(self.runtime, entered=entered, release=release)
        other_runtime = new_runtime(Path(self.tmp.name))
        second = simple_agent(other_runtime, marker="other-run")
        pending = asyncio.create_task(first.invoke_async("first"))
        await entered.wait()
        await second.invoke_async("second")
        same_run_peer = simple_agent(self.runtime, "news_analyst")
        await same_run_peer.invoke_async("peer")
        self.assertFalse(pending.done())
        release.set()
        await pending
        self.assertNotIn("other-run", str(self.runtime.store.read_snapshot().values))

    async def test_foreign_round_rejected_before_memory_prompt_or_conversation_reset(
        self,
    ):
        start = self.runtime.store.begin_debate(
            manager_id="research_manager",
            manager_invocation_id=uuid4().hex,
            operation_id=uuid4().hex,
        )
        other = new_runtime(Path(self.tmp.name))
        child = simple_agent(other, "bull_researcher")
        child.messages.append({"role": "user", "content": [{"text": "keep"}]})
        memory = Mock()
        child.lifecycle_hooks.memory = memory
        context = RoundContext(
            start.handle.debate_id,
            1,
            "opening",
            "bull_researcher",
            start.snapshot,
            start.handle.run_id,
            start.handle.manager_id,
            start.handle.manager_invocation_id,
            start.handle.generation,
            uuid4().hex,
        )
        with self.assertRaises(RunContextMismatch):
            await child.invoke_async(
                "foreign", invocation_state={"debate_context": context}
            )
        self.assertEqual(child.messages[0]["content"][0]["text"], "keep")
        memory.search_memories.assert_not_called()
        self.assertFalse(child.model.calls)

    async def test_manager_overlap_and_memory_failure_keep_complete_round(self):
        fixture = test_debates.DebateIntegrationTests()
        fixture.runtime, fixture.calls = self.runtime, []
        manager, hook, participants = fixture.build()
        failing = participants["bear_researcher"].lifecycle_hooks.memory
        failing.add_memory.side_effect = RuntimeError("memory failure")
        with self.assertRaises(RuntimeError):
            await manager.invoke_async("Analyze")
        snapshot = self.runtime.store.read_snapshot().values
        self.assertIn("Round 1 (opening)", snapshot["research_debate_history"])
        for participant in hook.spec.workflow.participants:
            self.assertIn(participant.report_key, snapshot)
        self.assertNotIn("research_manager_report", snapshot)
        self.assertFalse(
            any(call["agent_id"] == "research_manager" for call in fixture.calls)
        )
        # Cleanup released the ownership slot, but its generation stays fenced.
        fresh = self.runtime.store.begin_debate(
            manager_id="research_manager",
            manager_invocation_id=uuid4().hex,
            operation_id=uuid4().hex,
        )
        self.assertEqual(fresh.handle.generation, 2)

    async def test_all_real_agents_complete_with_isolated_sessions_and_no_legacy_access(
        self,
    ):
        import main

        calls = []
        clients = []
        real_open = builtins.open
        legacy = [
            REPO_ROOT / "data" / name
            for name in (
                "shared_document.json",
                "agents_sessions",
                "chroma_memories",
                "market_data",
                "news_data",
                "fundamentals_data",
            )
        ]
        fixture_data = Path(self.tmp.name) / "data"
        sentinels = []
        for name in (
            "shared_document.json",
            "agents_sessions/old.json",
            "chroma_memories/old.json",
            "market_data/old.json",
        ):
            path = fixture_data / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"sentinel": "legacy-must-not-be-read"}', encoding="utf-8")
            sentinels.append((path, path.read_bytes()))
            legacy.append(path)

        def guarded_open(file, *args, **kwargs):
            if isinstance(file, (str, os.PathLike)):
                path = Path(file).absolute()
                if any(path == root or path.is_relative_to(root) for root in legacy):
                    raise AssertionError("Legacy analysis access")
            return real_open(file, *args, **kwargs)

        def fake_mcp(*args, **kwargs):
            client = Mock()
            client.list_tools_sync.return_value = []
            clients.append(client)
            return client

        with ExitStack() as stack:
            stack.enter_context(patch("runtime.mcp.MCPClient", side_effect=fake_mcp))
            stack.enter_context(patch("builtins.open", side_effect=guarded_open))
            stack.enter_context(patch("io.open", side_effect=guarded_open))
            for agent_id, spec in AGENT_SPECS.items():
                name = (
                    ".".join(spec.prompt_path.parent.relative_to(REPO_ROOT).parts)
                    + ".agent"
                )
                module = importlib.import_module(name)
                stack.enter_context(
                    patch.object(
                        module,
                        "OpenAIModel",
                        side_effect=lambda _id=agent_id, **_: WorkflowModel(_id, calls),
                    )
                )
            with patch("sys.stdout", new_callable=io.StringIO):
                result = await main.run_analysis(
                    "AAPL", "2025-08-01", output_root=fixture_data / "runs"
                )
        self.assertEqual(result.status, "SUCCEEDED")
        state = json.loads(result.state_path.read_text(encoding="utf-8"))
        for spec in AGENT_SPECS.values():
            for key in spec.output_keys:
                self.assertIn(key, state)
        self.assertEqual(state["trader_report"], state["trader_investment_plan"])
        self.assertEqual(state["risk_manager_report"], state["final_trade_decision"])
        self.assertEqual(
            {path.parent.name for path in (result.run_root / "sessions").glob("*/*")},
            set(AGENT_SPECS),
        )
        self.assertTrue(all(run_id == result.run_id for _, run_id in calls))
        self.assertEqual(len(clients), 7)
        for client in clients:
            client.stop.assert_called_once_with(None, None, None)
        self.assertFalse((result.run_root / "memory").exists())
        for path, original in sentinels:
            self.assertEqual(path.read_bytes(), original)
        self.assertNotIn("legacy-must-not-be-read", str(state))

    async def test_child_tool_failures_remain_fatal_after_parent_final_report(self):
        for failure_kind in ("model", "memory"):
            with self.subTest(failure=failure_kind):
                runtime = create_run(
                    RunConfig("AAPL", "2025-08-01", output_root=Path(self.tmp.name))
                )
                fixture = test_debates.DebateIntegrationTests()
                fixture.runtime, fixture.calls = runtime, []
                observed = {}
                closed = Mock()

                def factory(*, runtime):
                    runtime.resources.register(closed)
                    manager, hook, participants = fixture.build(
                        failure=(1, "error") if failure_kind == "model" else None
                    )
                    if failure_kind == "memory":
                        participants[
                            "bear_researcher"
                        ].lifecycle_hooks.memory.add_memory.side_effect = RuntimeError(
                            "private-fixture-error"
                        )

                    @tool
                    async def research(message: str) -> str:
                        """Run the research manager for an analysis request."""
                        return str(await manager.invoke_async(message))

                    parent_hook = AgentLifecycleHooks(
                        AGENT_SPECS["investment_manager"], runtime=runtime
                    )
                    parent = RunAgent(
                        runtime=runtime,
                        agent_id="investment_manager",
                        model=WorkflowModel("investment_manager"),
                        hooks=[parent_hook],
                        tools=[research],
                        callback_handler=None,
                    )
                    parent.lifecycle_hooks = parent_hook
                    observed["parent"] = parent
                    return parent

                with self.assertRaises(RunExecutionError) as caught:
                    await runtime.execute(
                        factory, "Analyze", "investment_manager_report"
                    )
                self.assertEqual(caught.exception.status, "FAILED")
                snapshot = runtime.store.read_snapshot().values
                # The SDK did recover into a parent report; runtime still rejects success.
                self.assertIn("investment_manager_report", snapshot)
                tool_results = [
                    block["toolResult"]
                    for message in observed["parent"].messages
                    for block in message.get("content", [])
                    if "toolResult" in block
                ]
                self.assertEqual(tool_results[0]["status"], "error")
                self.assertNotIn("research_manager_report", snapshot)
                self.assertEqual(
                    "research_debate_history" in snapshot, failure_kind == "memory"
                )
                record = runtime.store.inspect()
                self.assertEqual(record["status"], "FAILED")
                self.assertFalse(record["artifacts"])
                self.assertIn(
                    record["primary_error"]["agent_id"],
                    {"bear_researcher", "research_manager"},
                )
                self.assertRegex(
                    record["primary_error"]["invocation_id"], r"^[a-f0-9]{32}$"
                )
                self.assertNotIn(
                    "private-fixture-error",
                    runtime.context.path("manifest.json").read_text(),
                )
                self.assertFalse(runtime._invocations)
                closed.assert_called_once()

    async def test_credentials_reach_model_but_not_manifest_or_database_diagnostics(
        self,
    ):
        from agents.traders.trader import agent as module

        credentials = {
            "TRADERS_API_KEY": "fixture-credential-for-isolation",  # pragma: allowlist secret
            "TRADERS_BASE_URL": "https://fixture-user:fixture-password@example.invalid/v1?secret=fixture-query#fixture-fragment",  # pragma: allowlist secret
            "TRADERS_MODEL_ID": "offline-model",
        }
        config = RunConfig(
            "AAPL",
            "2025-08-01",
            output_root=Path(self.tmp.name),
            models=resolve_models(credentials),
        )
        runtime = create_run(config)
        with patch.object(
            module, "OpenAIModel", return_value=WorkflowModel("trader")
        ) as model:
            await runtime.execute(module.Trader, "Analyze", "trader_report")
        self.assertEqual(
            model.call_args.kwargs["client_args"],
            {
                "base_url": credentials["TRADERS_BASE_URL"],
                "api_key": credentials["TRADERS_API_KEY"],
            },
        )
        manifest = runtime.context.path("manifest.json").read_text()
        record = runtime.store.inspect()
        for secret in (
            "fixture-credential-for-isolation",
            "fixture-password",
            "fixture-query",
            "fixture-fragment",
        ):
            self.assertNotIn(secret, manifest)
            self.assertNotIn(secret, str(record))
        self.assertIn("offline-model", manifest)
        self.assertIn("prompt_hashes", manifest)
        self.assertIn("lockfile_hash", manifest)

    async def test_every_a2a_entry_point_rejects_before_side_effects(self):
        paths = (
            list((REPO_ROOT / "agents").rglob("main.py"))
            + list((REPO_ROOT / "agents").rglob("test_a2a.py"))
            + list((REPO_ROOT / "agents").rglob("a2a_agent.py"))
        )
        for path in paths:
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                namespace = runpy.run_path(str(path))
                if path.name == "main.py":
                    with self.assertRaises(UnsupportedExecutionMode):
                        namespace["a2a_agent_app"]()
                elif path.name == "test_a2a.py":
                    with self.assertRaises(UnsupportedExecutionMode):
                        await namespace["send_sync_message"]("test")
                else:
                    cls = next(
                        cls
                        for cls in namespace.values()
                        if isinstance(cls, type) and cls.__module__ == "<run_path>"
                    )
                    with self.assertRaises(UnsupportedExecutionMode):
                        cls()
                with self.assertRaises(UnsupportedExecutionMode):
                    runpy.run_path(str(path), run_name="__main__")

    async def test_both_debates_interleave_across_runs_with_frozen_snapshots(self):
        runtimes = [self.runtime, new_runtime(Path(self.tmp.name))]
        barriers = {number: asyncio.Barrier(4) for number in (1, 2, 3)}
        fixtures = []
        tasks = []
        for runtime in runtimes:
            marker = runtime.context.run_id
            snapshot = runtime.store.read_snapshot()
            runtime.store.patch_reports(
                agent_id="market_analyst",
                invocation_id=uuid4().hex,
                operation_id=uuid4().hex,
                changes={"market_analyst_report": marker},
                expected_revisions={
                    "market_analyst_report": snapshot.revisions.get(
                        "market_analyst_report", 0
                    )
                },
            )
            for manager_id in ("research_manager", "risk_manager"):
                fixture = test_debates.DebateIntegrationTests()
                fixture.runtime, fixture.calls = runtime, []
                manager, hook, participants = fixture.build(manager_id)
                fixtures.append((fixture, hook.spec.workflow))
                first = hook.spec.workflow.participants[0].agent_id
                for participant_id, child in participants.items():
                    original = child.model.stream

                    async def stream(
                        *args,
                        _original=original,
                        _first=participant_id == first,
                        _marker=marker,
                        **kwargs,
                    ):
                        context = kwargs["invocation_state"]["debate_context"]
                        if _first:
                            await asyncio.wait_for(
                                barriers[context.round_number].wait(), 10
                            )
                        async for event in _original(*args, **kwargs):
                            delta = event.get("contentBlockDelta", {}).get("delta", {})
                            if "text" in delta:
                                delta["text"] = _marker + ": " + delta["text"]
                            yield event

                    child.model.stream = stream
                tasks.append(asyncio.create_task(manager.invoke_async("Analyze")))
        await asyncio.wait_for(asyncio.gather(*tasks), 30)
        for fixture, policy in fixtures:
            marker = fixture.runtime.context.run_id
            for number in (1, 2, 3):
                calls = [call for call in fixture.calls if call["round"] == number]
                self.assertEqual(len(calls), len(policy.participants))
                self.assertTrue(
                    all(call["snapshot"] == calls[0]["snapshot"] for call in calls)
                )
                self.assertEqual(calls[0]["snapshot"]["market_analyst_report"], marker)
                self.assertNotIn(
                    f"Round {number} (",
                    calls[0]["snapshot"].get(policy.history_key, ""),
                )
            history = fixture.runtime.store.read_snapshot().values[policy.history_key]
            self.assertIn(marker, history)
            self.assertNotIn(
                next(r.context.run_id for r in runtimes if r is not fixture.runtime),
                history,
            )

    async def test_queued_manager_stream_does_not_clear_active_conversation(self):
        fixture = test_debates.DebateIntegrationTests()
        fixture.runtime, fixture.calls = self.runtime, []
        manager, hook, participants = fixture.build()
        child = participants["bull_researcher"]
        entered, release, queued = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original = child.model.stream

        async def blocked(*args, **kwargs):
            if not entered.is_set():
                entered.set()
                await release.wait()
            async for event in original(*args, **kwargs):
                yield event

        child.model.stream = blocked

        async def second_call():
            queued.set()
            return [event async for event in manager.stream_async("Second")]

        with patch.object(
            self.runtime.store, "begin_debate", wraps=self.runtime.store.begin_debate
        ) as begin:
            first = asyncio.create_task(manager.invoke_async("First"))
            await asyncio.wait_for(entered.wait(), 10)
            messages = list(child.messages)
            second = asyncio.create_task(second_call())
            await queued.wait()
            self.assertEqual(begin.call_count, 1)
            self.assertEqual(child.messages, messages)
            release.set()
            await asyncio.wait_for(asyncio.gather(first, second), 20)
            self.assertEqual(begin.call_count, 2)
        self.assertEqual(
            sum(call["agent_id"] == "research_manager" for call in fixture.calls), 2
        )
        self.assertEqual(sum(call["round"] is not None for call in fixture.calls), 12)

    async def test_standalone_factory_allocates_fresh_run_and_batch_returns_failure(
        self,
    ):
        from runtime.examples import run_example

        # run_example owns asyncio.run, so run it outside this test's event loop.
        def factory(*, runtime):
            return simple_agent(runtime)

        with (
            patch.object(sys, "argv", ["example", "--output-root", self.tmp.name]),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            first = await asyncio.to_thread(
                run_example, factory, "market_analyst_report"
            )
            second = await asyncio.to_thread(
                run_example, factory, "market_analyst_report"
            )
        self.assertNotEqual(first.run_id, second.run_id)
        import main

        error = RunExecutionError(
            self.runtime.context,
            "FAILED",
            __import__("runtime.errors", fromlist=["SafeError"]).SafeError(
                "ExecutionFailure", "invocation"
            ),
        )

        async def fail(*args):
            raise error

        with (
            patch.object(main, "run_analysis", side_effect=fail),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            status = await asyncio.to_thread(main.main)
        self.assertEqual(status, 1)


class ProcessIsolationTests(unittest.TestCase):
    def test_independent_spawned_runs_isolate_state_sessions_cache_and_errors(self):
        with TemporaryDirectory() as tmp:
            ctx = multiprocessing.get_context("spawn")
            queue, barrier = ctx.Queue(), ctx.Barrier(2)
            workers = [
                ctx.Process(
                    target=independent_worker, args=(tmp, marker, barrier, queue)
                )
                for marker in ("sentinel-A", "sentinel-B")
            ]
            try:
                for worker in workers:
                    worker.start()
                results = [queue.get(timeout=60) for _ in workers]
                for worker in workers:
                    worker.join(timeout=15)
                    self.assertEqual(worker.exitcode, 0)
                self.assertEqual([status for status, _, _ in results], ["ok", "ok"])
                for _, root, marker in results:
                    text = "".join(
                        p.read_text(encoding="utf-8") for p in root.rglob("*.json")
                    )
                    self.assertIn(marker, text)
                    self.assertNotIn(
                        "sentinel-B" if marker == "sentinel-A" else "sentinel-A", text
                    )
                    self.assertTrue(list((root / "sessions").rglob("*.json")))
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                        worker.join(timeout=10)
                queue.close()

    def test_spawned_managers_cannot_claim_same_slot(self):
        with TemporaryDirectory() as tmp:
            runtime = new_runtime(Path(tmp))
            ctx = multiprocessing.get_context("spawn")
            queue, barrier = ctx.Queue(), ctx.Barrier(2)
            workers = [
                ctx.Process(
                    target=overlapping_manager_worker,
                    args=(runtime.context, barrier, queue),
                )
                for _ in range(2)
            ]
            try:
                for worker in workers:
                    worker.start()
                results = [queue.get(timeout=60) for _ in workers]
                self.assertCountEqual(results, ["owner", "conflict"])
                for worker in workers:
                    worker.join(timeout=15)
                    self.assertEqual(worker.exitcode, 0)
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                        worker.join(timeout=10)
                queue.close()


if __name__ == "__main__":
    unittest.main()
