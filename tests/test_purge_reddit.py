"""Offline contracts for the Reddit purge tool."""

import io
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from utils.purge_reddit import REDACTED, main, purge, run_status


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def tool_use(tool_id, name):
    return {"toolUse": {"toolUseId": tool_id, "name": name, "input": {}}}


def tool_result(tool_id, text):
    return {
        "toolResult": {
            "toolUseId": tool_id,
            "status": "success",
            "content": [{"text": text}],
        }
    }


def make_session(root):
    messages = root / "news_analyst" / "s1" / "agents" / "agent_news" / "messages"
    write_json(
        messages / "message_1.json",
        {
            "message": {
                "role": "assistant",
                "content": [
                    tool_use("r1", "get_reddit_news"),
                    tool_use("f1", "get_finnhub_news"),
                ],
            }
        },
    )
    write_json(
        messages / "message_2.json",
        {
            "message": {
                "role": "user",
                "content": [
                    tool_result("r1", "reddit post body"),
                    tool_result("f1", "finnhub headline"),
                ],
            }
        },
    )
    return messages / "message_2.json"


def make_run(runs_root, name, status):
    root = runs_root / name
    root.mkdir(parents=True)
    with closing(sqlite3.connect(root / "run.sqlite3")) as db:
        db.execute("CREATE TABLE run (status TEXT NOT NULL)")
        db.execute("INSERT INTO run VALUES (?)", (status,))
        db.commit()
    write_json(root / "cache" / "reddit-news-data-server" / "a.json", {"data": []})
    write_json(root / "cache" / "finnhub-news-data-server" / "b.json", {"data": []})
    return root, make_session(root / "sessions")


def results(path):
    return {
        block["toolResult"]["toolUseId"]: block["toolResult"]["content"][0]["text"]
        for block in read_json(path)["message"]["content"]
    }


class PurgeRedditTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root / "runs"
        self.done, self.done_message = make_run(self.runs, "done", "SUCCEEDED")
        self.live, self.live_message = make_run(self.runs, "live", "RUNNING")
        self.legacy = self.root / "legacy"
        write_json(self.legacy / "news_data" / "reddit_news_AAPL_x.json", {})
        write_json(self.legacy / "news_data" / "finnhub_news_AAPL_x.json", {})
        self.legacy_message = make_session(self.legacy / "agents_sessions")

    def test_dry_run_reports_without_changing_files(self):
        report = purge(self.runs)
        self.assertEqual(
            report.cache_dirs, [self.done / "cache" / "reddit-news-data-server"]
        )
        self.assertEqual(report.redacted_messages, [self.done_message])
        self.assertTrue((self.done / "cache" / "reddit-news-data-server").exists())
        self.assertEqual(results(self.done_message)["r1"], "reddit post body")

    def test_apply_purges_finished_runs_only(self):
        report = purge(self.runs, apply=True)
        self.assertFalse((self.done / "cache" / "reddit-news-data-server").exists())
        self.assertTrue((self.done / "cache" / "finnhub-news-data-server").exists())
        self.assertEqual(
            results(self.done_message), {"r1": REDACTED, "f1": "finnhub headline"}
        )
        self.assertEqual(report.skipped_runs, [(self.live, "RUNNING")])
        self.assertTrue((self.live / "cache" / "reddit-news-data-server").exists())
        self.assertEqual(results(self.live_message)["r1"], "reddit post body")
        # Legacy data is untouched unless requested.
        self.assertTrue(
            (self.legacy / "news_data" / "reddit_news_AAPL_x.json").exists()
        )
        self.assertEqual(results(self.legacy_message)["r1"], "reddit post body")

    def test_apply_preserves_legacy_and_rerun_is_idempotent(self):
        before = {
            path: path.read_bytes() for path in self.legacy.rglob("*") if path.is_file()
        }
        purge(self.runs, apply=True)
        self.assertEqual(before, {path: path.read_bytes() for path in before})
        again = purge(self.runs, apply=True)
        self.assertEqual((again.cache_dirs, again.redacted_messages), ([], []))
        with (
            patch("sys.stderr", new_callable=io.StringIO),
            self.assertRaises(SystemExit) as caught,
        ):
            main(["--include-legacy", "--apply"])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_named_abandoned_run_can_be_purged_without_changing_status(self):
        other, other_message = make_run(self.runs, "another", "CREATED")
        dry = purge(self.runs, abandoned_runs=["live"])
        self.assertIn(self.live / "cache" / "reddit-news-data-server", dry.cache_dirs)
        self.assertTrue((self.live / "cache" / "reddit-news-data-server").exists())
        purge(self.runs, abandoned_runs=["live"], apply=True)
        self.assertFalse((self.live / "cache" / "reddit-news-data-server").exists())
        self.assertEqual(results(self.live_message)["r1"], REDACTED)
        self.assertEqual(run_status(self.live), "RUNNING")
        self.assertTrue((other / "cache" / "reddit-news-data-server").exists())
        self.assertEqual(results(other_message)["r1"], "reddit post body")

    def test_run_without_readable_status_is_skipped(self):
        broken = self.runs / "broken"
        write_json(broken / "cache" / "reddit-news-data-server" / "c.json", {})
        report = purge(self.runs, apply=True)
        self.assertIn((broken, None), report.skipped_runs)
        self.assertTrue((broken / "cache" / "reddit-news-data-server").exists())

    def test_sentiment_tool_results_are_redacted_alongside_legacy_news(self):
        request = self.done_message.with_name("message_1.json")
        data = read_json(request)
        data["message"]["content"].append(tool_use("s1", "get_reddit_sentiment"))
        write_json(request, data)
        data = read_json(self.done_message)
        data["message"]["content"].append(tool_result("s1", "reddit opinion sample"))
        write_json(self.done_message, data)
        purge(self.runs, apply=True)
        self.assertEqual(
            results(self.done_message),
            {
                "r1": REDACTED,
                "s1": REDACTED,
                "f1": "finnhub headline",
            },
        )


if __name__ == "__main__":
    unittest.main()
