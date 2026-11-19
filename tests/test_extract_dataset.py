import importlib.util
import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from http.client import IncompleteRead
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch
from urllib.error import URLError

import pandas as pd

from runtime.core.errors import InvalidRunConfig
from runtime.providers.capture import window_coverage, write_slice
from runtime.providers.timecut import format_instant
from runtime.store.artifacts import hash_file
from utils.extract_dataset import (
    STATEMENTS,
    build,
    capture,
    child_environment,
    copy_key,
    last_closed_friday,
    run_provider,
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


FAKE_SOURCES = """
import json
import sys
from pathlib import Path

from runtime.providers.capture import run_cli

SOURCES = sys.argv.pop(1).split(",")
GAPS = Path(__file__).parent / "gaps.json"


def coverage(request, raw):
    gaps = json.loads(GAPS.read_text(encoding="utf-8")) if GAPS.exists() else []
    return {
        item["date"]: {source: {"coverage_rule_met": True} for source in SOURCES}
        for item in request["candidates"]
        if item["date"] not in gaps
    }


raise SystemExit(run_cli(lambda request, output: None, lambda request, raw: [], coverage=coverage))
"""


def load_service(name: str, path: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    return service


def candidate(day: str, cutoff: str) -> dict[str, str]:
    return {"date": day, "cutoff": cutoff, "execution": day, "exit": day}


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
        sources = self.root / "fake_sources.py"
        sources.write_text(FAKE_SOURCES, encoding="utf-8")
        self.commands = {
            "yfinance": [sys.executable, "-B", str(self.script)],
            "edgar": [
                sys.executable,
                "-B",
                str(sources),
                "edgar_balance,edgar_cashflow,edgar_income",
            ],
            "finnhub_fundamentals": [
                sys.executable,
                "-B",
                str(sources),
                "insider_transactions,insider_sentiment",
            ],
            "finnhub_news": [sys.executable, "-B", str(sources), "finnhub_news"],
            "gdelt": [sys.executable, "-B", str(sources), "gdelt_news"],
            "reddit": [sys.executable, "-B", str(sources), "reddit_posts"],
        }
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

    def test_only_fetch_loads_provider_env_file(self) -> None:
        with patch("utils.extract_dataset.subprocess.run") as run:
            for action in ("fetch", "normalize"):
                run_provider(STATEMENTS, action, {}, self.root, None)
        fetch, normalize = (call.args[0] for call in run.call_args_list)
        self.assertIn("--env-file", fetch)
        self.assertNotIn("--env-file", normalize)

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

    def test_provider_gap_excludes_date_from_shared_calendar(self) -> None:
        (self.root / "gaps.json").write_text('["2026-01-09"]', encoding="utf-8")
        self.run_capture({"AAPL": self.days})
        self.run_build()
        manifest = self.manifest()
        self.assertNotIn("2026-01-09", [item["date"] for item in manifest["dates"]])
        self.assertIn("2026-01-09", manifest["coverage_summary"]["excluded_dates"])

    def test_empty_price_history_is_not_marked_finished(self) -> None:
        service = load_service(
            "yfin_capture_service",
            "mcp-servers/yfin-market-data-server/services/yfin_service.py",
        )
        output = self.root / "raw"
        with patch.object(service.yf, "Ticker") as ticker:
            ticker.return_value.history.return_value = pd.DataFrame()
            with self.assertRaises(ValueError):
                service.fetch({"ticker": "AAPL"}, output)
        self.assertFalse((output / "history.done").exists())


EDGAR_PATH = "mcp-servers/simfin-fundamentals-data-server/services/edgar_service.py"
FUNDAMENTALS = "mcp-servers/finnhub-fundamentals-data-server/services"


def fact(accn: str, filed: str, end: str, val: int, start: str = "") -> dict:
    form, fp = ("10-K", "FY") if accn == "k" else ("10-Q", "Q2")
    row = {"accn": accn, "form": form, "fp": fp, "filed": filed, "end": end}
    return {**row, "val": val, **({"start": start} if start else {})}


class FundamentalsCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.raw = Path(folder.name)

    def test_edgar_statements_use_each_filings_own_period(self) -> None:
        service = load_service("edgar_capture_service", EDGAR_PATH)
        units = {
            "NetIncomeLoss": [
                fact("q2", "2026-04-30", "2026-03-28", 10, "2025-12-28"),
                fact("q2", "2026-04-30", "2026-03-28", 25, "2025-09-28"),
                fact("k", "2025-10-31", "2025-09-27", 40, "2024-09-29"),
                fact("k", "2025-10-31", "2025-09-27", 12, "2025-06-29"),
            ],
            "NetCashProvidedByUsedInOperatingActivities": [
                fact("q2", "2026-04-30", "2026-03-28", 60, "2025-09-28"),
                fact("q2", "2026-04-30", "2026-03-28", 110, "2025-03-30"),
            ],
            "Assets": [
                fact("q2", "2026-04-30", "2026-03-28", 300),
                fact("q2", "2026-04-30", "2026-03-28", 200, "2025-09-28"),
                fact("q2", "2026-04-30", "2025-09-27", 200),
            ],
        }
        gaap = {name: {"units": {"USD": rows}} for name, rows in units.items()}
        write_slice(self.raw, "companyfacts", {"facts": {"us-gaap": gaap}})
        records = {(r.source, r.id): r for r in service.normalize({}, self.raw)}
        key = "quarterly|2026-03-28|2026-04-30"
        quarter = records["edgar_income", key]
        self.assertEqual(quarter.payload["NetIncomeLoss"], 10)
        self.assertEqual(format_instant(quarter.public_at), "2026-05-01T03:59:59Z")
        cash = records["edgar_cashflow", key].payload
        self.assertEqual(cash["Period Start"], "2025-09-28")
        self.assertEqual(cash["NetIncomeLoss"], 25)
        self.assertEqual(cash["NetCashProvidedByUsedInOperatingActivities"], 60)
        annual = records["edgar_income", "annual|2025-09-27|2025-10-31"]
        self.assertEqual(annual.payload["NetIncomeLoss"], 40)
        self.assertEqual(records["edgar_balance", key].payload["Assets"], 300)

        fresh = candidate("2026-08-28", "2026-08-28T04:00:00Z")
        stale = candidate("2026-09-04", "2026-09-04T04:00:00Z")
        entries = service.coverage({"candidates": [fresh, stale]}, self.raw)
        self.assertTrue(entries["2026-08-28"]["edgar_income"]["coverage_rule_met"])
        self.assertFalse(entries["2026-09-04"]["edgar_income"]["coverage_rule_met"])

    def test_insider_transactions_split_saturated_pages(self) -> None:
        service = load_service(
            "insider_transactions_capture",
            f"{FUNDAMENTALS}/insider_transactions_service.py",
        )
        rows = [
            {"id": str(n), "name": "A", "filingDate": "2026-01-05"} for n in range(3)
        ]
        late = {"id": "9", "transactionDate": "2025-10-01", "filingDate": "2026-01-20"}

        def transactions(ticker: str, start: str, end: str) -> dict:
            found = [r for r in [*rows, late] if start <= r["filingDate"] <= end]
            return {"data": found}

        request = {
            "ticker": "AAPL",
            "candidates": [candidate("2026-01-23", "2026-01-23T05:00:00Z")],
        }
        key = {"FINNHUB_API_KEY": "fixture"}  # pragma: allowlist secret
        with (
            patch.dict(os.environ, key),
            patch.object(service, "INSIDER_PAGE_MAX", 2),
            patch.object(service.finnhub, "Client") as client,
        ):
            client.return_value.stock_insider_transactions.side_effect = transactions
            service.fetch(request, self.raw)
            entry = service.coverage(request, self.raw)["2026-01-23"]
        self.assertTrue(entry["truncated"])
        self.assertFalse(entry["coverage_rule_met"])
        old_page = {
            "start": "2025-11-24",
            "end": "2025-11-24",
            "saturated": True,
            "rows": [],
        }
        late_lag = window_coverage(
            [], [old_page], request["candidates"][0], 30, 2, 0, 30
        )
        self.assertFalse(late_lag["coverage_rule_met"])
        filed = {r.id.split("|")[0]: r for r in service.normalize(request, self.raw)}
        self.assertEqual(format_instant(filed["9"].public_at), "2026-01-21T04:59:59Z")

    def test_insider_sentiment_is_public_on_third_weekday(self) -> None:
        service = load_service(
            "insider_sentiment_capture",
            f"{FUNDAMENTALS}/insider_sentiment_service.py",
        )
        write_slice(self.raw, "insider_sentiment", [{"year": 2025, "month": 12}])
        (record,) = service.normalize({}, self.raw)
        self.assertEqual(record.id, "2025-12")
        self.assertEqual(format_instant(record.public_at), "2026-01-06T04:59:59Z")


GDELT_PATH = "mcp-servers/gdelt-news-data-server/services/gdelt_news_service.py"
NEWS_PATH = "mcp-servers/finnhub-news-data-server/services/finnhub_news_service.py"


class NewsCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.raw = Path(folder.name) / "ticker"
        self.request = {
            "ticker": "AAPL",
            "candidates": [candidate("2026-01-09", "2026-01-09T05:00:00Z")],
        }

    def test_finnhub_news_is_public_at_its_epoch(self) -> None:
        service = load_service("finnhub_news_capture", NEWS_PATH)
        rows = [{"id": 7, "datetime": 1767934800}, {"id": 8, "datetime": None}]
        write_slice(
            self.raw,
            "finnhub_news-2026-01-02-2026-01-08",
            {
                "start": "2026-01-02",
                "end": "2026-01-08",
                "saturated": False,
                "rows": rows,
            },
        )
        (record,) = service.normalize(self.request, self.raw)
        self.assertEqual(format_instant(record.public_at), "2026-01-09T05:00:00Z")
        entry = service.coverage(self.request, self.raw)["2026-01-09"]["finnhub_news"]
        self.assertEqual((entry["records"], entry["dropped_rows"]), (1, 1))
        self.assertTrue(entry["coverage_rule_met"])

    def test_gdelt_cuts_late_articles_and_keeps_truncated_window(self) -> None:
        service = load_service("gdelt_capture", GDELT_PATH)
        early = {"url": "u1", "seendate": "20260109T050000Z", "title": "Apple"}
        late = {"url": "u2", "seendate": "20260109T050100Z", "title": "Apple"}
        filler = [{"url": f"m{n}", "seendate": "20260105T120000Z"} for n in range(250)]
        write_slice(self.raw, "ticker-2026-01-09", [early, late])
        write_slice(self.raw.parent / "macro", "macro-2026-01-09", filler)
        urls = {r.payload["url"] for r in service.normalize(self.request, self.raw)}
        self.assertIn("u1", urls)
        self.assertNotIn("u2", urls)
        entry = service.coverage(self.request, self.raw)["2026-01-09"]["gdelt_news"]
        self.assertTrue(entry["truncated"])
        self.assertTrue(entry["coverage_rule_met"])

    def test_gdelt_exhausted_retries_leave_window_unreachable(self) -> None:
        service = load_service("gdelt_retry_capture", GDELT_PATH)
        with (
            patch.object(service.time, "sleep"),
            patch.object(
                service,
                "urlopen",
                side_effect=[URLError("refused"), *[IncompleteRead(b"")] * 4] * 2,
            ),
        ):
            service.fetch(self.request, self.raw)
        entry = service.coverage(self.request, self.raw)["2026-01-09"]["gdelt_news"]
        self.assertFalse(entry["reachable"])
        self.assertFalse(entry["coverage_rule_met"])


REDDIT_PATH = "mcp-servers/reddit-news-data-server/services/reddit_news_service.py"


class RedditCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.raw = Path(folder.name)
        self.service = load_service("reddit_capture", REDDIT_PATH)
        self.request = {
            "ticker": "AAPL",
            "candidates": [candidate("2026-01-09", "2026-01-09T05:00:00Z")],
        }

    def write_searches(self, reached: set[str]) -> Path:
        raw = self.raw / "-".join(sorted(reached))
        recent = datetime(2026, 1, 8, tzinfo=timezone.utc).timestamp()
        old = datetime(2025, 12, 1, tzinfo=timezone.utc).timestamp()
        for name in self.service.SENTIMENT_SUBREDDITS:
            for variant in ("symbol", "cashtag", "name"):
                posts = [
                    {"id": f"{name}{variant}{n}", "created_utc": recent}
                    for n in range(200)
                ]
                if name in reached:
                    posts.append({"id": f"{name}{variant}old", "created_utc": old})
                write_slice(raw, f"{name}-{variant}", posts)
        return raw

    def test_posts_hold_no_engagement_and_200_posts_are_capped(self) -> None:
        recent = datetime(2026, 1, 8, tzinfo=timezone.utc).timestamp()
        self.assertTrue(self.service.search_reached([{}] * 199, recent))
        self.assertFalse(self.service.search_reached([{}] * 200, recent))
        raw = self.write_searches(set())
        record = self.service.normalize(self.request, raw)[0]
        self.assertNotIn("score", record.payload)
        self.assertNotIn("num_comments", record.payload)

    def test_three_of_five_active_subreddits_must_reach_lookback(self) -> None:
        def met(reached: set[str]) -> bool:
            raw = self.write_searches(reached)
            entries = self.service.coverage(self.request, raw)
            return entries["2026-01-09"]["reddit_posts"]["coverage_rule_met"]

        self.assertFalse(met({"stocks", "investing", "finance"}))
        self.assertTrue(met({"stocks", "investing", "options"}))


if __name__ == "__main__":
    unittest.main()
