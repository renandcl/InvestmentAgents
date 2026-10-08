"""Offline regression tests; run with python -m unittest discover -s tests."""

import inspect
import json
import runpy
import tempfile
import tomllib
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class State(dict):
    def set(self, key, value):
        self[key] = value


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.shared = Path(self.temp.name) / "shared.json"
        self.data = {
            "ticker": "AAPL",
            "current_date": "2025-08-01",
            "fundamentals_analyst_report": 'Original fundamentals {"value": 1}',
            "market_analyst_report": "Original market",
            "news_analyst_report": "Original news",
            "bear_researcher_report": "Original bear",
            "bull_researcher_report": "Original bull",
            "research_manager_report": "Original research",
            "trader_investment_plan": "Original trade",
        }
        self.save_data()

    def save_data(self):
        self.shared.write_text(json.dumps(self.data), encoding="utf-8")

    def make_hook(self, folder):
        cls = runpy.run_path(str(ROOT / folder / "hook.py"))["SharedDocument"]
        kwargs = {"shared_document_file": str(self.shared)}
        if "memory" in inspect.signature(cls).parameters:
            kwargs["memory"] = Mock(search_memories=Mock(return_value=[]))
        hook = cls(**kwargs)
        agent = SimpleNamespace(
            system_prompt=(ROOT / folder / "prompt.txt").read_text(encoding="utf-8"),
            state=State(),
            messages=[{"role": "user", "content": [{"text": "Analyze"}]}],
            agent_id=hook.spec.agent_id,
        )
        return hook, SimpleNamespace(agent=agent)

    def test_all_hooks_render_fresh_state_on_repeated_invocations(self):
        for path in sorted((ROOT / "agents").rglob("hook.py")):
            with self.subTest(hook=str(path.relative_to(ROOT))):
                hook, event = self.make_hook(path.parent.relative_to(ROOT))
                template = event.agent.system_prompt
                hook.get_shared_document(event)
                hook.add_prompt_arguments(event)
                self.data["market_analyst_report"] = 'Updated market {"value": 2}'
                self.data["bear_researcher_report"] = "Updated bear"
                self.data["ticker"] = "MSFT"
                self.save_data()
                hook.get_shared_document(event)
                hook.add_prompt_arguments(event)
                self.assertEqual(event.agent.state["system_prompt"], template)
                if "{market_analyst_report}" in template:
                    self.assertIn(
                        self.data["market_analyst_report"], event.agent.system_prompt
                    )
                if "{bear_researcher_report}" in template:
                    self.assertIn("Updated bear", event.agent.system_prompt)
                if "{ticker}" in template:
                    self.assertIn("MSFT", event.agent.system_prompt)

    def test_research_report_reaches_trader(self):
        hook, event = self.make_hook(Path("agents/researchers/manager"))
        hook.get_shared_document(event)
        event.agent.messages = [
            {"role": "assistant", "content": [{"text": "Buy ten shares"}]}
        ]
        event.result = SimpleNamespace(
            stop_reason="end_turn", message=event.agent.messages[-1]
        )
        hook.save_shared_document(event)
        trader, event = self.make_hook(Path("agents/traders/trader"))
        trader.get_shared_document(event)
        trader.add_prompt_arguments(event)
        self.assertIn(
            "Proposed Investment Plan: Buy ten shares", event.agent.system_prompt
        )
        self.assertIn("Buy ten shares", trader.memory.search_memories.call_args.args[0])

    def test_managers_count_results_before_rendering_without_counting_retries(self):
        for folder in ("agents/researchers/manager", "agents/risk_mgt/risk_manager"):
            with self.subTest(manager=folder):
                hook, event = self.make_hook(Path(folder))
                hook.get_shared_document(event)
                hook.prepare_model_call(event)
                self.assertEqual(event.agent.state["debate_rounds"], 0)
                event.agent.messages = []
                hook.prepare_model_call(event)
                for round_number in range(1, 4):
                    event.agent.messages.append(
                        {
                            "role": "user",
                            "content": [
                                {"text": "Tool results"},
                                {
                                    "toolResult": {
                                        "toolUseId": f"round-{round_number}-a",
                                        "status": "success",
                                    }
                                },
                                {
                                    "toolResult": {
                                        "toolUseId": f"round-{round_number}-b",
                                        "status": "success",
                                    }
                                },
                            ],
                        }
                    )
                    hook.prepare_model_call(event)
                    hook.prepare_model_call(event)
                    self.assertEqual(event.agent.state["debate_rounds"], round_number)
                    self.assertIn(
                        f"Number of Debate Rounds: {round_number}",
                        event.agent.system_prompt,
                    )
                self.assertIn("Debate Action: Make final", event.agent.system_prompt)
                event.agent.messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"toolResult": {"toolUseId": "failed", "status": "error"}},
                        ],
                    }
                )
                hook.prepare_model_call(event)
                self.assertEqual(event.agent.state["debate_rounds"], 3)
                hook.get_shared_document(event)
                self.assertEqual(event.agent.state["debate_rounds"], 0)

    def test_manager_refreshes_research_reports_between_tool_turns(self):
        hook, event = self.make_hook(Path("agents/researchers/manager"))
        hook.get_shared_document(event)
        self.data["bear_researcher_report"] = "Latest rebuttal"
        self.save_data()
        hook.add_prompt_arguments(event)
        self.assertIn("Latest rebuttal", event.agent.system_prompt)


class RedditTests(unittest.TestCase):
    def test_first_fetch_matches_cached_results_and_filters_dates(self):
        namespace = runpy.run_path(
            str(
                ROOT
                / "mcp-servers/reddit-news-data-server/services/reddit_news_service.py"
            )
        )
        service = namespace["RedditNewsService"].__new__(namespace["RedditNewsService"])
        posts = [
            SimpleNamespace(
                title=title,
                selftext="Body",
                created_utc=datetime.fromisoformat(date).timestamp(),
            )
            for title, date in [
                ("Matching article", "2025-08-19"),
                ("Too old", "2025-01-01"),
                ("Future", "2025-08-21"),
            ]
        ]
        search = Mock(return_value=iter(posts))
        service.reddit = SimpleNamespace(
            subreddit=lambda _: SimpleNamespace(search=search)
        )
        globals_ = service.get_news.__globals__
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "news.json"
            overrides = {
                "open": lambda _, mode: cache.open(mode, encoding="utf-8"),
                "os": SimpleNamespace(
                    path=SimpleNamespace(exists=lambda _: cache.exists()),
                    makedirs=Mock(),
                ),
                "Submission": lambda _, _data: SimpleNamespace(**_data),
            }
            with patch.dict(globals_, overrides):
                first = service.get_news("AAPL", "2025-08-20", 30)
                cached = service.get_news("AAPL", "2025-08-20", 30)
            self.assertEqual(first, cached)
            self.assertIn("Matching article", first)
            self.assertNotIn("Too old", first)
            self.assertNotIn("Future", first)
            search.assert_called_once()


class WorkspaceTests(unittest.TestCase):
    def test_every_workspace_member_exists(self):
        config = tomllib.loads((ROOT / "pyproject.toml").read_text())
        for member in config["tool"]["uv"]["workspace"]["members"]:
            self.assertTrue((ROOT / member / "pyproject.toml").is_file(), member)


if __name__ == "__main__":
    unittest.main()
