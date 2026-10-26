"""Persistent reuse is explicit, committed, scoped and isolated from live writers."""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from test_run_store import publish

from agents.hooks.contracts import ContractError
from runtime.artifacts import export_final
from runtime.context import MemoryMode, RunConfig
from runtime.lifecycle import RunRuntime, create_run
from runtime.long_term_memory import (
    MEMORY_LIMIT,
    MEMORY_VERSION,
    load_seeds,
    memory_texts,
    snapshot_artifacts,
)
from runtime.types import ArtifactRecord


def completed_source(
    root: Path,
    date: str,
    *,
    ticker: str = "AAPL",
    agent_id: str = "trader",
    texts: tuple[str, ...] = ("earlier fact",),
    mode: MemoryMode = MemoryMode.PERSISTENT,
    outcome: str = "SUCCEEDED",
    sources: tuple[dict[str, str], ...] = (),
) -> RunRuntime:
    runtime = create_run(RunConfig(ticker, date, output_root=root, memory_mode=mode))
    runtime.store.transition("CREATED", "RUNNING")
    publish(runtime.store, "investment_manager", "decision")
    path = runtime.context.path("memory", agent_id, "long_term.json")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": MEMORY_VERSION,
                "run_id": runtime.context.run_id,
                "ticker": ticker,
                "agent_id": agent_id,
                "analysis_date": date,
                "memories": texts,
                "sources": sources,
            }
        ),
        encoding="utf-8",
    )
    if outcome == "SUCCEEDED":
        snapshot = runtime.store.read_snapshot()
        artifacts = export_final(runtime.context, snapshot)
        if mode == MemoryMode.PERSISTENT:
            data = path.read_bytes()
            artifacts.append(
                ArtifactRecord(
                    f"memory/{agent_id}/long_term.json",
                    f"memory:{agent_id}",
                    hashlib.sha256(data).hexdigest(),
                    len(data),
                    snapshot.sequence,
                )
            )
        runtime.store.commit_success(
            artifacts=artifacts,
            required_report_key="investment_manager_report",
            expected_sequence=snapshot.sequence,
        )
    elif outcome != "RUNNING":
        runtime.store.transition("RUNNING", outcome)
    return runtime


class PersistentSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def target(self, date: str = "2026-02-01") -> RunRuntime:
        return create_run(RunConfig("AAPL", date, output_root=self.root))

    def test_default_and_successful_earlier_scope(self) -> None:
        self.assertEqual(
            RunConfig("AAPL", "2026-01-01").memory_mode, MemoryMode.PERSISTENT
        )
        source = completed_source(self.root, "2026-01-01")
        seed = load_seeds(self.target(), "trader")
        self.assertEqual(seed["memories"], ["earlier fact"])
        self.assertEqual(seed["sources"][0]["run_id"], source.context.run_id)

    def test_other_scopes_dates_and_unsuccessful_runs_are_excluded(self) -> None:
        for options in (
            {"ticker": "MSFT"},
            {"agent_id": "bull_researcher"},
            {"mode": MemoryMode.RUN_ONLY},
            {"outcome": "FAILED"},
            {"outcome": "CANCELLED"},
            {"outcome": "RUNNING"},
        ):
            completed_source(self.root, "2026-01-01", **options)
        completed_source(self.root, "2026-02-01")
        completed_source(self.root, "2026-03-01")
        self.assertEqual(load_seeds(self.target(), "trader")["memories"], [])

    def test_sources_finishing_after_creation_are_excluded(self) -> None:
        target = self.target()
        completed_source(self.root, "2026-01-01")
        self.assertEqual(load_seeds(target, "trader")["sources"], [])

    def test_concurrent_branches_merge_without_duplicate_texts(self) -> None:
        completed_source(self.root, "2026-01-01", texts=("A", "common"))
        completed_source(self.root, "2026-01-02", texts=("B", "common"))
        seed = load_seeds(self.target(), "trader")
        self.assertEqual(seed["memories"], ["A", "B", "common"])
        self.assertEqual(len(seed["sources"]), 2)

    def test_corruption_fails_closed(self) -> None:
        source = completed_source(self.root, "2026-01-01")
        source.context.path("memory", "trader", "long_term.json").write_text("{}")
        with self.assertRaises(ContractError):
            load_seeds(self.target(), "trader")

    def test_descendant_replaces_ancestor_memory_instead_of_resurrecting_it(
        self,
    ) -> None:
        ancestor = completed_source(self.root, "2026-01-01", texts=("obsolete fact",))
        receipt = next(
            item
            for item in ancestor.store.inspect()["artifacts"]
            if item["kind"] == "memory:trader"
        )
        completed_source(
            self.root,
            "2026-01-02",
            texts=("updated fact",),
            sources=(
                {
                    "run_id": ancestor.context.run_id,
                    "sha256": receipt["sha256"],
                },
            ),
        )
        self.assertEqual(
            load_seeds(self.target(), "trader")["memories"], ["updated fact"]
        )

    def test_snapshot_limit_fails_instead_of_silently_truncating(self) -> None:
        with self.assertRaises(ContractError):
            memory_texts([f"fact {index}" for index in range(MEMORY_LIMIT)])

    def test_altered_memory_cannot_commit_success(self) -> None:
        runtime = self.target()
        runtime.store.transition("CREATED", "RUNNING")
        publish(runtime.store, "investment_manager", "decision")
        runtime._memories["trader"] = SimpleNamespace()
        path = runtime.context.path("memory", "trader", "long_term.json")
        path.parent.mkdir(parents=True)
        path.write_text("original")
        snapshot = runtime.store.read_snapshot()
        artifacts = export_final(runtime.context, snapshot) + snapshot_artifacts(
            runtime, snapshot.sequence
        )
        path.write_text("changed")
        with self.assertRaises(ContractError):
            runtime.store.commit_success(
                artifacts=artifacts,
                required_report_key="investment_manager_report",
                expected_sequence=snapshot.sequence,
            )
        self.assertEqual(runtime.store.status(), "RUNNING")
        self.assertEqual(runtime.store.inspect()["artifacts"], [])


class PersistentWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_vector_memory_survives_across_private_runs(self) -> None:
        real_popen = subprocess.Popen

        def offline_worker(command: list[str], **options: Any) -> subprocess.Popen[str]:
            command = (
                command[:2]
                + [
                    "-c",
                    "import runpy; runpy.run_path('tests/offline_memory_worker.py', run_name='__main__')",
                ]
                + command[4:]
            )
            return real_popen(command, **options)

        class RememberingAgent:
            def __init__(self, *, runtime: RunRuntime) -> None:
                self.runtime = runtime

            async def invoke_async(self, message: str) -> SimpleNamespace:
                memory = self.runtime.memory_for("trader")
                before = memory.search_memories("query", "AAPL", n_matches=100)[
                    "results"
                ]
                self.runtime.before = [row["memory"] for row in before]
                assert all(
                    row["user_id"] == self.runtime.context.run_id
                    and row["agent_id"] == "trader"
                    for row in before
                )
                memory.add_memory(message, "AAPL")
                publish(self.runtime.store, "investment_manager", "decision")
                return SimpleNamespace(stop_reason="end_turn")

        with (
            TemporaryDirectory() as temporary,
            patch("runtime.memory.subprocess.Popen", side_effect=offline_worker),
        ):
            root = Path(temporary)
            earlier = create_run(RunConfig("AAPL", "2026-01-01", output_root=root))
            await earlier.execute(
                RememberingAgent, "earlier", "investment_manager_report"
            )
            self.assertEqual(earlier.before, [])
            path = earlier.context.path("memory", "trader", "long_term.json")
            original = path.read_bytes()
            later = create_run(RunConfig("AAPL", "2026-02-01", output_root=root))
            await later.execute(RememberingAgent, "later", "investment_manager_report")
            self.assertIn(f"sentinel-{earlier.context.run_id}-trader", later.before)
            self.assertEqual(path.read_bytes(), original)
            self.assertNotEqual(
                earlier._memories["trader"].root, later._memories["trader"].root
            )
            self.assertTrue(
                later.context.path(
                    "memory", "trader", "chroma", "chroma.sqlite3"
                ).is_file()
            )
            self.assertTrue(
                later.context.path("memory", "trader", "history.sqlite3").is_file()
            )
            self.assertIn(
                "memory:trader",
                {row["kind"] for row in later.store.inspect()["artifacts"]},
            )
