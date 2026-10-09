"""Offline contracts for allocation and SQLite ownership, including spawned writers."""

import concurrent.futures
import hashlib
import multiprocessing
import os
import sqlite3
import threading
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from agents.hooks.contracts import ContractError
from agents.hooks.specs import AGENT_SPECS
from runtime.context import RunConfig, allocate_context, resolve_models
from runtime.errors import (
    DuplicateOperationConflict,
    InvalidRunConfig,
    RunAlreadyExists,
    RunContextMismatch,
    RunNotWritable,
    SafeError,
    StateConflict,
    StateStoreUnavailable,
    UnsafeRunPath,
)
from runtime.store import RunStore
from runtime.types import ArtifactRecord, Contribution

PROVENANCE = {
    "code_revision": None,
    "dirty": None,
    "lockfile_hash": None,
    "prompt_hashes": {},
}


def make_store(root, *, start=True):
    config = RunConfig("AAPL", "2026-01-01", output_root=Path(root))
    context = allocate_context(config)
    store = RunStore(context)
    store.initialize(config, PROVENANCE)
    if start:
        store.transition("CREATED", "RUNNING")
    return store


def publish(
    store,
    agent_id,
    report="report",
    *,
    invocation=None,
    operation=None,
    expected=None,
    handle=None,
):
    changes = dict.fromkeys(AGENT_SPECS[agent_id].output_keys, report)
    snapshot = store.read_snapshot()
    return store.patch_reports(
        agent_id=agent_id,
        invocation_id=invocation or uuid4().hex,
        operation_id=operation or uuid4().hex,
        changes=changes,
        expected_revisions=(
            expected
            if expected is not None
            else {key: snapshot.revisions.get(key, 0) for key in changes}
        ),
        debate_handle=handle,
    )


def spawned_publish(context, barrier, agent_id, queue):
    try:
        store = RunStore(context)
        barrier.wait(timeout=15)
        publish(store, agent_id, agent_id)
        queue.put("ok")
    except Exception as error:
        queue.put(type(error).__name__)


class ContextTests(unittest.TestCase):
    def test_fresh_identity_and_collision_leaves_bytes_unchanged(self):
        with TemporaryDirectory() as tmp:
            config = RunConfig(
                "../AAPL", "2026-01-01", output_root=Path(tmp) / "space á"
            )
            fixed = uuid4()
            a = allocate_context(config, id_factory=lambda: fixed)
            sentinel = a.path("sentinel")
            sentinel.write_bytes(b"untouched")
            b = allocate_context(config)
            self.assertNotEqual(a.run_root, b.run_root)
            with self.assertRaises(RunAlreadyExists):
                allocate_context(config, id_factory=lambda: fixed)
            self.assertEqual(sentinel.read_bytes(), b"untouched")
            self.assertNotIn("AAPL", str(a.run_root))

    def test_invalid_configuration_has_no_allocation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "absent"
            for kwargs in (
                {"ticker": ""},
                {"current_date": "20260101"},
                {"busy_timeout": float("nan")},
                {"memory_mode": "GLOBAL"},
            ):
                values = {
                    "ticker": "AAPL",
                    "current_date": "2026-01-01",
                    "output_root": root,
                } | kwargs
                with self.assertRaises(InvalidRunConfig):
                    RunConfig(**values)
            self.assertFalse(root.exists())

    def test_containment_rejects_injected_components_and_real_redirect(self):
        with TemporaryDirectory() as tmp:
            context = allocate_context(
                RunConfig("AAPL", "2026-01-01", output_root=Path(tmp) / "runs")
            )
            for name in ("..", "../escape", "a/b", "C:\\escape", "/absolute", "a:b"):
                with self.assertRaises(UnsafeRunPath):
                    context.path(name)
            target = Path(tmp) / "foreign"
            target.mkdir()
            link = context.path("redirect")
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                # Windows junctions do not require developer mode or symlink privileges.
                import subprocess

                completed = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "New-Item -ItemType Junction -ErrorAction Stop -Path '"
                        + str(link).replace("'", "''")
                        + "' -Target '"
                        + str(target).replace("'", "''")
                        + "' | Out-Null",
                    ],
                    capture_output=True,
                    check=False,
                )
                if completed.returncode:
                    self.skipTest("Host cannot create a symlink/junction fixture")
            with self.assertRaises(UnsafeRunPath):
                context.path("redirect", "escape")
            link.rmdir() if os.name == "nt" and not link.is_symlink() else link.unlink()

    def test_model_snapshot_preserves_blank_defaults_and_overrides(self):
        settings = resolve_models(
            {
                "ANALYSTS_MODEL_ID": "",
                "ANALYSTS_BASE_URL": "",
                "ANALYSTS_API_KEY": "",
                "TRADERS_MODEL_ID": "other",
            }
        )
        self.assertEqual(settings[0].model_id, "qwen3:8b")
        self.assertEqual(settings[0].base_url, "http://localhost:11434/v1")
        self.assertEqual(settings[0].api_key, "ollama")
        self.assertEqual(settings[2].model_id, "other")
        self.assertNotIn("api_key", repr(settings))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = make_store(self.tmp.name)

    def start_debate(self, manager="research_manager"):
        return self.store.begin_debate(
            manager_id=manager,
            manager_invocation_id=uuid4().hex,
            operation_id=uuid4().hex,
        )

    def commit_round(self, start, number, **overrides):
        policy = AGENT_SPECS[start.handle.manager_id].workflow
        snapshot = self.store.read_snapshot()
        keys = [p.report_key for p in policy.participants] + [policy.history_key]
        args = {
            "debate_handle": start.handle,
            "operation_id": uuid4().hex,
            "round_number": number,
            "contributions": {
                p.agent_id: Contribution(
                    f"round-{number}-{p.agent_id}", uuid4().hex, uuid4().hex
                )
                for p in policy.participants
            },
            "expected_revisions": {key: snapshot.revisions.get(key, 0) for key in keys},
        } | overrides
        return self.store.commit_round(**args), args

    def test_round_readers_never_observe_partial_publication_or_rollback(self):
        for fail in (False, True):
            with self.subTest(rollback=fail):
                start = self.start_debate()
                self.commit_round(start, 1)
                previous = self.store.read_snapshot()
                entered, release = threading.Event(), threading.Event()
                original = self.store._write

                def pause_write(db, key, *args):
                    result = original(db, key, *args)
                    if not entered.is_set():
                        entered.set()
                        if not release.wait(timeout=10):
                            raise TimeoutError("Test reader did not release writer")
                        if fail:
                            raise RuntimeError("Injected mid-transaction failure")
                    return result

                with patch.object(self.store, "_write", side_effect=pause_write):
                    with concurrent.futures.ThreadPoolExecutor(1) as pool:
                        future = pool.submit(self.commit_round, start, 2)
                        try:
                            self.assertTrue(entered.wait(timeout=10))
                            self.assertEqual(self.store.read_snapshot(), previous)
                        finally:
                            release.set()
                        if fail:
                            with self.assertRaises(RuntimeError):
                                future.result(timeout=10)
                        else:
                            future.result(timeout=10)
                current = self.store.read_snapshot()
                if fail:
                    self.assertEqual(current, previous)
                else:
                    for participant in AGENT_SPECS[
                        "research_manager"
                    ].workflow.participants:
                        self.assertEqual(
                            current.values[participant.report_key],
                            f"round-2-{participant.agent_id}",
                        )
                    self.assertIn(
                        "Round 2 (rebuttal)", current.values["research_debate_history"]
                    )
                self.store.end_debate(debate_handle=start.handle, outcome="aborted")

    def test_unrelated_thread_writes_both_survive(self):
        barrier = threading.Barrier(2)

        def write(agent_id):
            barrier.wait(timeout=10)
            return publish(self.store, agent_id, agent_id)

        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = [
                pool.submit(write, agent)
                for agent in ("market_analyst", "news_analyst")
            ]
            for future in futures:
                future.result(timeout=15)
        snapshot = self.store.read_snapshot()
        self.assertEqual(snapshot.values["market_analyst_report"], "market_analyst")
        self.assertEqual(snapshot.values["news_analyst_report"], "news_analyst")

    def test_spawned_process_writes_both_survive(self):
        ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        workers = [
            ctx.Process(
                target=spawned_publish, args=(self.store.context, barrier, agent, queue)
            )
            for agent in ("market_analyst", "news_analyst")
        ]
        try:
            for worker in workers:
                worker.start()
            self.assertEqual([queue.get(timeout=30) for _ in workers], ["ok", "ok"])
            for worker in workers:
                worker.join(timeout=15)
                self.assertEqual(worker.exitcode, 0)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=10)
            queue.close()
        self.assertEqual(
            self.store.read_snapshot().values["market_analyst_report"], "market_analyst"
        )
        self.assertEqual(
            self.store.read_snapshot().values["news_analyst_report"], "news_analyst"
        )

    def test_stale_revision_and_changed_operation_fail_without_lost_update(self):
        operation, invocation = uuid4().hex, uuid4().hex
        first = publish(
            self.store, "trader", "plan", operation=operation, invocation=invocation
        )
        expected = dict.fromkeys(AGENT_SPECS["trader"].output_keys, 0)
        duplicate = publish(
            self.store,
            "trader",
            "plan",
            operation=operation,
            invocation=invocation,
            expected=expected,
        )
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(first.event_sequence, duplicate.event_sequence)
        with self.assertRaises(DuplicateOperationConflict):
            publish(
                self.store,
                "trader",
                "changed",
                operation=operation,
                invocation=invocation,
                expected=expected,
            )
        with self.assertRaises(StateConflict):
            publish(self.store, "trader", "stale", expected=expected)
        state = self.store.read_snapshot().values
        self.assertEqual(state["trader_report"], state["trader_investment_plan"])
        self.assertEqual(state["trader_report"], "plan")

    def test_missing_alias_or_foreign_key_rejected(self):
        for changes in (
            {"trader_report": "plan"},
            {"ticker": "OTHER"},
            {"trader_report": "x", "trader_investment_plan": "y"},
        ):
            with self.assertRaises(ContractError):
                self.store.patch_reports(
                    agent_id="trader",
                    invocation_id="invocation",
                    operation_id=uuid4().hex,
                    changes=changes,
                    expected_revisions=dict.fromkeys(changes, 0),
                )

    def test_terminal_immutable_but_exact_receipt_can_be_read(self):
        invocation, operation = uuid4().hex, uuid4().hex
        receipt = publish(
            self.store, "market_analyst", invocation=invocation, operation=operation
        )
        self.store.transition(
            "RUNNING", "FAILED", error=SafeError("ExecutionFailure", "invocation")
        )
        with self.assertRaises(RunNotWritable):
            publish(self.store, "news_analyst")
        replay = publish(
            self.store,
            "market_analyst",
            invocation=invocation,
            operation=operation,
            expected={"market_analyst_report": 0},
        )
        self.assertTrue(replay.duplicate)
        self.assertEqual(replay.event_sequence, receipt.event_sequence)
        with self.assertRaises(RunNotWritable):
            self.store.transition("FAILED", "RUNNING")

    def test_busy_timeout_is_named_and_bounded(self):
        with closing(sqlite3.connect(self.store.context.database_path)) as held, held:
            held.execute("BEGIN IMMEDIATE")
            other = RunStore(self.store.context, timeout=0.02)
            with self.assertRaises(StateStoreUnavailable):
                publish(other, "market_analyst")
        self.assertNotIn("market_analyst_report", self.store.read_snapshot().values)

    def test_begin_reset_snapshot_and_replay_are_atomic_and_scoped(self):
        publish(self.store, "market_analyst", "untouched")
        publish(self.store, "bull_researcher", "old")
        invocation, operation = uuid4().hex, uuid4().hex
        start = self.store.begin_debate(
            manager_id="research_manager",
            manager_invocation_id=invocation,
            operation_id=operation,
        )
        self.assertNotIn("bull_researcher_report", start.snapshot.values)
        self.assertEqual(start.snapshot.revisions["bull_researcher_report"], 2)
        self.assertEqual(start.snapshot.values["market_analyst_report"], "untouched")
        self.commit_round(start, 1)
        replay = self.store.begin_debate(
            manager_id="research_manager",
            manager_invocation_id=invocation,
            operation_id=operation,
        )
        self.assertTrue(replay.receipt.duplicate)
        self.assertEqual(replay.snapshot, start.snapshot)
        self.assertIn("bull_researcher_report", self.store.read_snapshot().values)
        with self.assertRaises(StateConflict):
            self.start_debate()
        # Distinct managers may own their own slots concurrently.
        self.start_debate("risk_manager")

    def test_quorum_commit_and_no_partial_state_on_failure(self):
        start = self.start_debate()
        before = self.store.read_snapshot()
        with self.assertRaises(ContractError):
            self.commit_round(start, 1, contributions={})
        self.assertEqual(self.store.read_snapshot(), before)
        receipt, args = self.commit_round(start, 1)
        snapshot = self.store.read_snapshot()
        for p in AGENT_SPECS["research_manager"].workflow.participants:
            self.assertEqual(
                snapshot.values[p.report_key], args["contributions"][p.agent_id].report
            )
            self.assertIn(
                args["contributions"][p.agent_id].report,
                snapshot.values["research_debate_history"],
            )
        self.assertFalse(receipt.duplicate)
        self.assertTrue(self.store.commit_round(**args).duplicate)
        self.assertEqual(self.store.read_snapshot(), snapshot)

    def test_generation_fencing_and_monotonic_tombstones(self):
        first = self.start_debate()
        _, args = self.commit_round(first, 1)
        self.store.end_debate(debate_handle=first.handle, outcome="aborted")
        previous_revision = self.store.read_snapshot().revisions[
            "bull_researcher_report"
        ]
        second = self.start_debate()
        self.assertGreater(second.handle.generation, first.handle.generation)
        self.assertGreater(
            second.snapshot.revisions["bull_researcher_report"], previous_revision
        )
        with self.assertRaises(StateConflict):
            self.commit_round(first, 2)
        self.assertTrue(self.store.commit_round(**args).duplicate)
        self.assertNotIn("bull_researcher_report", self.store.read_snapshot().values)
        with self.assertRaises(StateConflict):
            publish(self.store, "bull_researcher", "late")

    def test_contribution_operation_cannot_be_reused_in_another_round(self):
        start = self.start_debate()
        _, args = self.commit_round(start, 1)
        before = self.store.read_snapshot()
        with self.assertRaises(DuplicateOperationConflict):
            self.commit_round(start, 2, contributions=args["contributions"])
        self.assertEqual(self.store.read_snapshot(), before)

    def test_foreign_and_stale_context_rejected_before_use(self):
        start = self.start_debate()
        params = {
            "handle": start.handle,
            "participant_id": "bull_researcher",
            "round_number": 1,
            "phase": "opening",
            "snapshot": start.snapshot,
        }
        self.store.validate_round(**params)
        with self.assertRaises(RunContextMismatch):
            self.store.validate_round(
                **(params | {"handle": replace(start.handle, run_id=uuid4().hex)})
            )
        self.commit_round(start, 1)
        with self.assertRaises(StateConflict):
            self.store.validate_round(**params)

    def test_synthesis_fenced_until_quorum_and_risk_aliases_atomic(self):
        start = self.start_debate("risk_manager")
        with self.assertRaises(StateConflict):
            publish(
                self.store,
                "risk_manager",
                invocation=start.handle.manager_invocation_id,
                handle=start.handle,
            )
        for number in range(1, 4):
            self.commit_round(start, number)
        with self.assertRaises(StateConflict):
            publish(self.store, "risk_manager", invocation="wrong", handle=start.handle)
        publish(
            self.store,
            "risk_manager",
            "decision",
            invocation=start.handle.manager_invocation_id,
            handle=start.handle,
        )
        self.store.end_debate(debate_handle=start.handle, outcome="completed")
        self.store.end_debate(debate_handle=start.handle, outcome="completed")
        snapshot = self.store.read_snapshot()
        self.assertEqual(snapshot.values["risk_manager_report"], "decision")
        self.assertEqual(snapshot.values["final_trade_decision"], "decision")
        self.assertIn("Round 3 (clarification)", snapshot.values["risk_debate_history"])

    def test_final_artifacts_required_and_hash_checked(self):
        publish(self.store, "investment_manager", "decision")
        snapshot = self.store.read_snapshot()
        artifacts = []
        for kind, name, data in (
            ("state", "shared_document.json", b"{}"),
            ("report", "report.md", b"decision"),
        ):
            self.store.context.path(name).write_bytes(data)
            artifacts.append(
                ArtifactRecord(
                    name,
                    kind,
                    hashlib.sha256(data).hexdigest(),
                    len(data),
                    snapshot.sequence,
                )
            )
        with self.assertRaises(RunNotWritable):
            self.store.transition("RUNNING", "SUCCEEDED")
        self.store.context.path("report.md").write_bytes(b"altered")
        with self.assertRaises(StateConflict):
            self.store.commit_success(
                artifacts=artifacts,
                required_report_key="investment_manager_report",
                expected_sequence=snapshot.sequence,
            )
        self.assertEqual(self.store.inspect()["artifacts"], [])
        self.store.context.path("report.md").write_bytes(b"decision")
        record = self.store.commit_success(
            artifacts=artifacts,
            required_report_key="investment_manager_report",
            expected_sequence=snapshot.sequence,
        )
        self.assertEqual(record["status"], "SUCCEEDED")
        self.assertEqual(len(record["artifacts"]), 2)
        with self.assertRaises(RunNotWritable):
            publish(self.store, "news_analyst")

    def test_store_rejects_same_id_with_altered_immutable_identity(self):
        foreign = RunStore(replace(self.store.context, ticker="OTHER"))
        with self.assertRaises(RunContextMismatch):
            foreign.read_snapshot()

    def test_safe_error_excludes_raw_exception(self):
        secret = "https://user:credential@host/path?api_key=credential"  # pragma: allowlist secret
        error = SafeError.from_exception(RuntimeError(secret), "invocation")
        self.store.transition("RUNNING", "FAILED", error=error)
        self.assertNotIn("credential", str(self.store.inspect()))


if __name__ == "__main__":
    unittest.main()
