"""Offline source separation and bounded Reddit evidence sampling."""

import json
import runpy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from isolation_helpers import new_runtime

from agents.analysts.news_analyst import agent as news_module
from agents.analysts.social_media import agent as social_module
from runtime.cache import RunCache
from runtime.context import REPO_ROOT


def post(post_id, date, subreddit="stocks"):
    return SimpleNamespace(
        id=post_id,
        title="Opinion " + post_id,
        selftext="Unverified bullish opinion",
        created_utc=datetime.fromisoformat(date)
        .replace(tzinfo=timezone.utc)
        .timestamp(),
        subreddit=SimpleNamespace(display_name=subreddit),
        permalink=f"/r/{subreddit}/comments/{post_id}/opinion/",
        score=5,
        num_comments=2,
    )


class SocialSentimentTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.runtime = new_runtime(Path(temporary.name))
        namespace = runpy.run_path(
            str(
                REPO_ROOT
                / "mcp-servers/reddit-news-data-server/services/reddit_news_service.py"
            )
        )
        cls = namespace["RedditNewsService"]
        self.service = cls.__new__(cls)
        self.service.cache = RunCache.for_run(self.runtime, "reddit-news-data-server")
        self.subreddits = namespace["SENTIMENT_SUBREDDITS"]

    def test_news_and_sentiment_have_disjoint_providers_and_tools(self):
        sentiment = SimpleNamespace(tool_name="get_reddit_sentiment")
        legacy_news = SimpleNamespace(tool_name="get_reddit_news")
        client = Mock()
        client.list_tools_sync.return_value = [sentiment, legacy_news]
        news = news_module.NewsAnalyst.__new__(news_module.NewsAnalyst)
        social = social_module.SocialMediaAnalyst.__new__(
            social_module.SocialMediaAnalyst
        )
        news.runtime = social.runtime = self.runtime
        with patch.object(news_module, "start_mcp", return_value=client) as start:
            news._init_mcps()
        self.assertEqual(
            [call.args[1] for call in start.call_args_list],
            [
                "finnhub-news-data-server",
                "duckduckgo-news-data-server",
            ],
        )
        with patch.object(social_module, "start_mcp", return_value=client) as start:
            social._init_mcps()
            social._init_tools()
        start.assert_called_once_with(
            self.runtime, "reddit-news-data-server", env_file=True
        )
        self.assertEqual(social.tools, [sentiment])

    def test_dated_deduplicated_sample_preserves_sources_and_cache(self):
        posts = [
            post("a", "2025-08-01T00:00:00"),
            post("b", "2025-08-20T23:59:59"),
            post("old", "2025-07-31T23:59:59"),
            post("future", "2025-08-21T00:00:00"),
        ]
        search = Mock(side_effect=lambda *args, **kwargs: iter(posts))
        self.service.reddit = Mock()
        self.service.reddit.subreddit.return_value.search = search
        first = self.service.get_sentiment(" aapl ", "2025-08-01", "2025-08-20")
        cached = self.service.get_sentiment("AAPL", "2025-08-01", "2025-08-20")
        self.assertEqual(first, cached)
        self.assertEqual([item["id"] for item in first["data"]], ["b", "a"])
        self.assertEqual(first["sample_size"], 2)
        self.assertEqual(first["timezone"], "UTC")
        self.assertEqual(first["status"], "ok")
        self.assertTrue(
            all(
                item["reddit_url"].startswith("https://www.reddit.com/r/")
                for item in first["data"]
            )
        )
        self.assertEqual(
            [call.args[0] for call in self.service.reddit.subreddit.call_args_list],
            list(self.subreddits),
        )
        self.assertEqual(search.call_count, len(self.subreddits))
        for call in search.call_args_list:
            self.assertEqual(call.args, ("AAPL",))
            self.assertEqual(
                call.kwargs, {"sort": "new", "time_filter": "all", "limit": 100}
            )
        smaller = self.service.get_sentiment(
            "AAPL", "2025-08-01", "2025-08-20", max_posts=1
        )
        self.assertEqual(smaller["sample_size"], 1)
        self.assertEqual(smaller["data"][0]["id"], "b")

    def test_empty_and_invalid_windows_never_imply_neutral_sentiment(self):
        self.service.reddit = Mock()
        self.service.reddit.subreddit.return_value.search.return_value = []
        result = self.service.get_sentiment("AAPL", "2025-08-01", "2025-08-20")
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["data"], [])
        self.assertIn("do not imply neutral", result["limitations"])
        self.service.reddit.reset_mock()
        for start, end, maximum in (
            ("2025-08-20", "2025-08-01", 30),
            ("2025-08-01", "2025-08-20", 0),
            ("2025-08-01", "2025-08-20", 101),
        ):
            with (
                self.subTest(start=start, maximum=maximum),
                self.assertRaises(ValueError),
            ):
                self.service.get_sentiment("AAPL", start, end, maximum)
        self.service.reddit.subreddit.assert_not_called()

    def test_mcp_sentiment_adapter_validates_dates_and_returns_structured_evidence(
        self,
    ):
        directory = REPO_ROOT / "mcp-servers/reddit-news-data-server"
        params = runpy.run_path(str(directory / "models/reddit_news_models.py"))[
            "RedditNewsParameters"
        ]
        service = Mock()
        service.get_sentiment.return_value = {"status": "no_data", "data": []}
        original_path = list(sys.path)
        self.addCleanup(setattr, sys, "path", original_path)
        with (
            patch("runtime.cache.provider_context", return_value=Mock()),
            patch.dict(
                sys.modules,
                {
                    "models": SimpleNamespace(RedditNewsParameters=params),
                    "services": SimpleNamespace(RedditNewsService=lambda: service),
                },
            ),
        ):
            module = runpy.run_path(str(directory / "main.py"))
        output = module["get_reddit_sentiment"](
            " aapl ", "2025-08-01", "2025-08-20", 12
        )
        self.assertEqual(json.loads(output), {"status": "no_data", "data": []})
        service.get_sentiment.assert_called_once_with(
            "AAPL", "2025-08-01", "2025-08-20", 12
        )
        service.reset_mock()
        with self.assertRaises(ValueError):
            module["get_reddit_sentiment"]("AAPL", "bad-date", "2025-08-20")
        service.get_sentiment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
