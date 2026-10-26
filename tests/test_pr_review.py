"""Offline regressions for PR correctness, artifact and timeout findings."""

import io
import json
import queue
import runpy
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from isolation_helpers import new_runtime
from test_run_lifecycle import ReportingAgent

import main
from agents.hooks.contracts import ContractError
from agents.hooks.specs import AGENT_SPECS
from runtime.artifacts import REPORT_AGENT_ORDER, render_report
from runtime.cache import RunCache
from runtime.context import REPO_ROOT, RunConfig
from runtime.errors import (
    InvalidRunConfig,
    RunAlreadyExists,
    RunExecutionError,
    RunNotWritable,
    StateConflict,
    StateStoreUnavailable,
)
from runtime.lifecycle import create_run
from runtime.memory import RunMemory


class ReviewUnitTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runtime = new_runtime(self.root)

    def test_status_checks_do_not_decode_full_inspection_and_observe_terminal_state(
        self,
    ):
        with patch.object(
            self.runtime.store, "inspect", side_effect=AssertionError("full inspection")
        ):
            self.runtime.assert_running()
            with self.runtime.store._transaction(write=True) as db:
                db.execute("UPDATE run SET status='FAILED'")
            with self.assertRaises(RunNotWritable):
                self.runtime.assert_running()

    def test_batch_counts_initialization_failures_and_continues(self):
        dates = main.pd.DatetimeIndex(["2025-08-01", "2025-08-08"])
        for error in (
            OSError("private"),
            InvalidRunConfig("private"),
            RunAlreadyExists("private"),
            StateStoreUnavailable("private"),
        ):
            with self.subTest(error=type(error).__name__):
                calls = []

                async def analyze(ticker, date):
                    calls.append((ticker, date))
                    if len(calls) == 1:
                        raise error
                    return SimpleNamespace(
                        run_id="fixture", status="SUCCEEDED", report_path="report.md"
                    )

                with (
                    patch.object(main, "run_analysis", side_effect=analyze),
                    patch.object(main.pd, "date_range", return_value=dates),
                    patch("sys.stdout", new_callable=io.StringIO) as output,
                ):
                    status = main.main()
                self.assertEqual(status, 1)
                self.assertEqual(len(calls), 14)
                self.assertIn("13 succeeded, 1 failed", output.getvalue())
                self.assertNotIn("private", output.getvalue())

    def test_report_follows_workflow_with_final_decision_last(self):
        values = self.runtime.store.read_snapshot().values
        values.update(
            {spec.output_keys[0]: agent for agent, spec in AGENT_SPECS.items()}
        )
        report = render_report(values)
        headers = [line for line in report.splitlines() if line.startswith("## ")]
        self.assertEqual(
            headers,
            [
                "## " + AGENT_SPECS[agent].output_keys[0].replace("_", " ").title()
                for agent in REPORT_AGENT_ORDER
            ],
        )
        self.assertEqual(headers[-1], "## Investment Manager Report")

    def test_finnhub_empty_responses_normalize_and_bad_responses_never_cache(self):
        namespace = runpy.run_path(
            str(
                REPO_ROOT
                / "mcp-servers/finnhub-fundamentals-data-server/services/insider_transactions_service.py"
            )
        )
        cls = namespace["FinnhubInsiderTransactionsService"]
        for index, response in enumerate(
            ({}, {"data": None}, {"data": []}, {"data": {}}, {"data": [None]}, [])
        ):
            with self.subTest(response=response):
                service = cls.__new__(cls)
                service.cache = RunCache.for_run(
                    self.runtime, "finnhub-fundamentals-data-server"
                )
                service.client = Mock()
                service.client.stock_insider_transactions.return_value = response
                ticker = f"FIXTURE{index}"
                key = service.cache.key(
                    "insider_transactions",
                    {
                        "ticker": ticker,
                        "before": "2025-07-21",
                        "current_date": "2025-08-20",
                    },
                )
                if index < 3:
                    first = service.get_insider_transactions(ticker, "2025-08-20", 30)
                    second = service.get_insider_transactions(ticker, "2025-08-20", 30)
                    self.assertEqual(first, second)
                    self.assertEqual(service.cache.read_json(key)["data"], [])
                    service.client.stock_insider_transactions.assert_called_once()
                else:
                    with self.assertRaises(ValueError):
                        service.get_insider_transactions(ticker, "2025-08-20", 30)
                    self.assertIsNone(service.cache.read_json(key))

    def test_memory_deadline_is_configurable_and_timeout_aborts_owned_worker(self):
        runtime = create_run(
            RunConfig(
                "AAPL", "2025-08-01", output_root=self.root, memory_request_timeout=3600
            )
        )
        runtime.store.transition("CREATED", "RUNNING")
        memory = RunMemory.__new__(RunMemory)
        memory.runtime = runtime
        memory.process = Mock()
        memory.process.poll.return_value = None
        memory._closed = False
        memory._lock = threading.Lock()
        memory._responses = Mock()
        memory._responses.get.return_value = '{"ok": true, "result": "done"}'
        with patch.object(memory, "abort") as abort:
            self.assertEqual(
                memory._request({"method": "add", "memory": "fixture"}), "done"
            )
            memory._responses.get.assert_called_once_with(timeout=3600)
            abort.assert_not_called()
            memory._responses.get.side_effect = queue.Empty
            with self.assertRaises(ContractError):
                memory._request({"method": "add", "memory": "fixture"})
            abort.assert_called_once()
        self.assertEqual(
            runtime.store.inspect()["config"]["memory_request_timeout"], 3600
        )
        for value in (0, -1, float("nan"), float("inf"), 86401, True):
            with self.subTest(timeout=value), self.assertRaises(InvalidRunConfig):
                RunConfig("AAPL", "2025-08-01", memory_request_timeout=value)


class ArtifactFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_export_never_claims_success_when_commit_fails(self):
        with TemporaryDirectory() as temporary:
            runtime = create_run(
                RunConfig("AAPL", "2025-08-01", output_root=Path(temporary))
            )
            with patch.object(
                runtime.store, "commit_success", side_effect=StateConflict("conflict")
            ):
                with self.assertRaises(RunExecutionError):
                    await runtime.execute(
                        ReportingAgent, "Decision", "investment_manager_report"
                    )
            state = json.loads(runtime.context.path("shared_document.json").read_text())
            self.assertNotIn("status", state)
            self.assertEqual(state["lifecycle_status_source"], "run.sqlite3")
            self.assertIn(
                "Analysis snapshot", runtime.context.path("report.md").read_text()
            )
            self.assertEqual(runtime.store.status(), "FAILED")
            self.assertFalse(runtime.store.inspect()["artifacts"])
            self.assertEqual(
                json.loads(runtime.context.path("manifest.json").read_text())["status"],
                "FAILED",
            )


if __name__ == "__main__":
    unittest.main()
