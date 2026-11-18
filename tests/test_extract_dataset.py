import importlib.util
import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from runtime.core.errors import InvalidRunConfig
from runtime.store.artifacts import hash_file
from utils.extract_dataset import (
    build,
    capture,
    child_environment,
    copy_key,
    last_closed_friday,
)

FAKE_PROVIDER = """
import json
import sys
from datetime import date
from pathlib import Path

from runtime.providers.capture import read_slice, run_cli, slice_finished, write_slice
from runtime.providers.timecut import Record, public_at_from_date

HERE = Path(__file__).parent


def fetch(request, output):
    if slice_finished(output, "history"):
        return
    with (HERE / "calls.log").open("a", encoding="utf-8") as log:
        log.write(request["ticker"] + "\\n")
    bars = json.loads((HERE / "bars.json").read_text(encoding="utf-8"))
    write_slice(output, "history", bars[request["ticker"]])


def normalize(request, raw):
    return [
        Record(day, public_at_from_date(date.fromisoformat(day)), "prices", {"Close": 10.0})
        for day in read_slice(raw, "history")
    ]


raise SystemExit(run_cli(fetch, normalize))
"""


def weekdays(start: date, end: date) -> list[str]:
    days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    return [day.isoformat() for day in days if day.weekday() < 5]


class ExtractDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.script = self.root / "fake_provider.py"
        self.script.write_text(FAKE_PROVIDER, encoding="utf-8")
        self.commands = {"yfinance": [sys.executable, "-B", str(self.script)]}
        self.days = weekdays(date(2025, 12, 1), date(2026, 1, 30))

    def run_capture(self, bars: dict[str, list[str]]) -> None:
        (self.root / "bars.json").write_text(json.dumps(bars), encoding="utf-8")
        capture(
            "cap",
            date(2025, 12, 8),
            date(2026, 1, 30),
            date(2025, 4, 1),
            tickers=tuple(bars),
            captures_root=self.root / "captures",
            provider_commands=self.commands,
        )

    def run_build(self, dataset_id: str = "study") -> str:
        return build(
            "cap",
            dataset_id,
            captures_root=self.root / "captures",
            datasets_root=self.root / "datasets",
            scoring_root=self.root / "scoring",
            provider_commands=self.commands,
        )

    def calls(self) -> list[str]:
        return (self.root / "calls.log").read_text(encoding="utf-8").splitlines()

    def manifest(self, dataset_id: str = "study") -> dict:
        path = self.root / "datasets" / dataset_id / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_capture_resumes_and_rebuild_makes_no_vendor_call(self) -> None:
        bars = {"AAPL": self.days, "MSFT": self.days}
        self.run_capture(bars)
        self.run_capture(bars)
        self.assertEqual(sorted(self.calls()), ["AAPL", "MSFT"])
        self.run_build("first")
        self.run_build("second")
        self.assertEqual(len(self.calls()), 2)

    def test_copy_holds_only_admitted_records(self) -> None:
        self.run_capture({"AAPL": self.days})
        digest = self.run_build()
        manifest_path = self.root / "datasets" / "study" / "manifest.json"
        self.assertEqual(digest, hash_file(manifest_path))
        day = self.manifest()["dates"][0]
        copy = self.root / "datasets/study/copies" / copy_key("AAPL", day["date"])
        prices = json.loads((copy / "prices.json").read_text(encoding="utf-8"))
        self.assertEqual(prices["records"][-1]["id"], "2025-12-11")
        self.assertEqual(day["date"], "2025-12-12")
        self.assertEqual(day["exit"], "2025-12-19")

    def test_scoring_stays_outside_dataset_and_is_hashed(self) -> None:
        self.run_capture({"AAPL": self.days})
        self.run_build()
        scoring = self.root / "scoring" / "study" / "scoring.json"
        self.assertEqual(
            self.manifest()["scoring"], {"scoring.json": hash_file(scoring)}
        )
        dataset_files = (self.root / "datasets" / "study").rglob("*")
        self.assertFalse(any(path.name == "scoring.json" for path in dataset_files))

    def test_build_refuses_existing_dataset_and_purged_capture(self) -> None:
        self.run_capture({"AAPL": self.days})
        self.run_build()
        with self.assertRaises(FileExistsError):
            self.run_build()
        (self.root / "captures" / "cap" / "purged.json").write_text(
            "{}", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            self.run_build("other")

    def test_one_tickers_gap_limits_the_shared_calendar(self) -> None:
        gap = [day for day in self.days if day != "2026-01-09"]
        self.run_capture({"AAPL": self.days, "MSFT": gap})
        self.run_build()
        manifest = self.manifest()
        dates = [item["date"] for item in manifest["dates"]]
        self.assertEqual(dates, ["2025-12-12", "2025-12-19", "2025-12-26"])
        excluded = manifest["coverage_summary"]["excluded_dates"]
        self.assertIn("2026-01-02", excluded)
        self.assertIn("2026-01-09", excluded)
        self.assertEqual({key.split("|")[1] for key in manifest["copies"]}, set(dates))

    def test_resumed_capture_refuses_different_arguments(self) -> None:
        self.run_capture({"AAPL": self.days})
        with self.assertRaises(ValueError):
            capture(
                "cap",
                date(2026, 1, 1),
                date(2026, 1, 30),
                date(2025, 4, 1),
                tickers=("AAPL",),
                captures_root=self.root / "captures",
                provider_commands=self.commands,
            )

    def test_identifiers_cannot_leave_their_storage_root(self) -> None:
        with self.assertRaises(InvalidRunConfig):
            capture(
                "../escape",
                date(2026, 1, 1),
                date(2026, 1, 30),
                date(2025, 4, 1),
                captures_root=self.root / "captures",
            )
        with self.assertRaises(InvalidRunConfig):
            build("cap", "../escape", captures_root=self.root / "captures")

    def test_friday_that_has_not_closed_is_not_scheduled(self) -> None:
        thursday = datetime(2026, 1, 8, 22, tzinfo=timezone.utc)
        before_close = datetime(2026, 1, 9, 20, tzinfo=timezone.utc)
        after_close = datetime(2026, 1, 9, 22, tzinfo=timezone.utc)
        self.assertEqual(last_closed_friday(thursday), date(2026, 1, 2))
        self.assertEqual(last_closed_friday(before_close), date(2026, 1, 2))
        self.assertEqual(last_closed_friday(after_close), date(2026, 1, 9))

    def test_only_fetch_receives_vendor_keys(self) -> None:
        keys = {
            "FINNHUB_API_KEY": "fixture",  # pragma: allowlist secret
            "REDDIT_CLIENT_ID": "fixture",
        }
        with patch.dict(os.environ, keys):
            self.assertIn("FINNHUB_API_KEY", child_environment("fetch"))
            offline = child_environment("normalize")
        self.assertNotIn("FINNHUB_API_KEY", offline)
        self.assertNotIn("REDDIT_CLIENT_ID", offline)

    def test_empty_price_history_is_not_marked_finished(self) -> None:
        path = Path("mcp-servers/yfin-market-data-server/services/yfin_service.py")
        spec = importlib.util.spec_from_file_location("yfin_capture_service", path)
        service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(service)
        output = self.root / "raw"
        with patch.object(service.yf, "Ticker") as ticker:
            ticker.return_value.history.return_value = pd.DataFrame()
            with self.assertRaises(ValueError):
                service.fetch({"ticker": "AAPL"}, output)
        self.assertFalse((output / "history.done").exists())


if __name__ == "__main__":
    unittest.main()
