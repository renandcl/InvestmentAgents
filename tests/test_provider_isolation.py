"""Private caches, actual stdio MCP children and early context rejection."""

import concurrent.futures
import importlib.util
import os
import runpy
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from isolation_helpers import new_runtime

from runtime.cache import CacheCorruption, RunCache, provider_context
from runtime.context import REPO_ROOT
from runtime.errors import (
    RunContextMismatch,
    RunContextRequired,
    UnsafeRunPath,
    UnsupportedExecutionMode,
)
from runtime.mcp import server_parameters, start_mcp


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runtime = new_runtime(Path(self.tmp.name))
        self.cache = RunCache.for_run(self.runtime, "finnhub-news-data-server")

    def test_hashed_canonical_keys_and_atomic_concurrent_publication(self):
        query = "../../../../outside/C:\\escape:á"
        key = self.cache.key("news", {"query": query, "count": 1})
        self.assertEqual(key, self.cache.key("news", {"count": 1, "query": query}))
        self.assertEqual(len(key), 69)
        self.assertNotIn(query, str(self.cache.path(key)))
        self.cache.write_json(key, {"data": ["initial"]})
        barrier = threading.Barrier(3)

        def writer(value):
            barrier.wait(timeout=5)
            for _ in range(10):
                self.cache.write_json(key, {"data": [value] * 100})

        def reader():
            barrier.wait(timeout=5)
            for _ in range(30):
                data = self.cache.read_json(key)["data"]
                self.assertEqual(len(set(data)), 1)

        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            for future in [
                pool.submit(writer, "A"),
                pool.submit(writer, "B"),
                pool.submit(reader),
            ]:
                future.result(timeout=15)
        self.assertEqual(
            list(self.cache.context.root.iterdir()), [self.cache.path(key)]
        )

    def test_malformed_cache_and_path_injection_fail(self):
        key = self.cache.key("news", {})
        for malformed in ("{", "[]", '{"wrong": []}'):
            self.cache.path(key).write_text(malformed, encoding="utf-8")
            with self.assertRaises(CacheCorruption):
                self.cache.read_json(key)
        with self.assertRaises(UnsafeRunPath):
            self.cache.read_text("../outside")

    @unittest.skipUnless(os.name == "nt", "Windows sharing semantics")
    def test_cache_permission_recovery_and_finite_exhaustion(self):
        key = self.cache.key("news", {})
        self.cache.write_json(key, {"data": ["previous"]})
        with (
            patch.object(
                Path,
                "read_text",
                side_effect=[PermissionError(), '{"data": ["complete"]}'],
            ) as read,
            patch("runtime.cache.time.sleep"),
        ):
            self.assertEqual(self.cache.read_json(key), {"data": ["complete"]})
            self.assertEqual(read.call_count, 2)
        with (
            patch.object(Path, "read_text", side_effect=PermissionError()) as read,
            patch("runtime.cache.time.monotonic", side_effect=[0, 0.5, 1.0]),
            patch("runtime.cache.time.sleep"),
        ):
            with self.assertRaises(PermissionError):
                self.cache.read_json(key)
            self.assertEqual(read.call_count, 2)
        real_replace = os.replace
        calls = []

        def transient_replace(source, target):
            calls.append(target)
            if len(calls) == 1:
                raise PermissionError()
            return real_replace(source, target)

        with (
            patch("runtime.artifacts.os.replace", side_effect=transient_replace),
            patch("runtime.artifacts.time.sleep"),
        ):
            self.cache.write_json(key, {"data": ["next"]})
        self.assertEqual(len(calls), 2)
        with (
            patch("runtime.artifacts.os.replace", side_effect=PermissionError()),
            patch("runtime.artifacts.time.monotonic", side_effect=[0, 0.5, 1.0]),
            patch("runtime.artifacts.time.sleep"),
        ):
            with self.assertRaises(PermissionError):
                self.cache.write_json(key, {"data": ["unpublished"]})
        self.assertEqual(self.cache.read_json(key), {"data": ["next"]})
        self.assertEqual(
            list(self.cache.context.root.iterdir()), [self.cache.path(key)]
        )

    def test_child_environment_preserves_parent_and_env_file_credentials(self):
        provider = "finnhub-news-data-server"
        root = Path(self.tmp.name) / "repository"
        server = root / "mcp-servers" / provider
        server.mkdir(parents=True)
        env_file = server / ".env"
        env_file.write_text(
            "FINNHUB_API_KEY=fixture-token\n",  # pragma: allowlist secret
            encoding="utf-8",
        )
        before = dict(os.environ)
        with patch("runtime.mcp.REPO_ROOT", root):
            params = server_parameters(self.runtime, provider, env_file=True)
            self.assertIn(str(env_file), params.args)
            self.assertEqual(
                params.env["INVESTMENT_RUN_ID"], self.runtime.context.run_id
            )
            self.assertEqual(
                params.env["INVESTMENT_CACHE_ROOT"], str(self.cache.context.root)
            )
            self.assertEqual(params.cwd, str(root))
            env_file.write_text("INVESTMENT_RUN_ID=foreign\n", encoding="utf-8")
            with self.assertRaises(RunContextMismatch):
                server_parameters(self.runtime, provider, env_file=True)
        self.assertEqual(dict(os.environ), before)

    def test_missing_and_mismatched_child_context_rejected(self):
        with patch.dict(
            os.environ, {"INVESTMENT_RUN_ID": "", "INVESTMENT_CACHE_ROOT": ""}
        ):
            with self.assertRaises(RunContextRequired):
                provider_context("finnhub-news-data-server")
        with patch.dict(
            os.environ,
            {
                "INVESTMENT_RUN_ID": self.runtime.context.run_id,
                "INVESTMENT_CACHE_ROOT": str(self.runtime.context.run_root),
            },
        ):
            with self.assertRaises(RunContextMismatch):
                provider_context("finnhub-news-data-server")

    def test_provider_bootstraps_and_legacy_report_demo_fail_before_initialization(
        self,
    ):
        original_path = list(sys.path)
        self.addCleanup(setattr, sys, "path", original_path)
        with patch.dict(
            os.environ, {"INVESTMENT_RUN_ID": "", "INVESTMENT_CACHE_ROOT": ""}
        ):
            for path in (REPO_ROOT / "mcp-servers").glob("*/main.py"):
                expected = (
                    UnsupportedExecutionMode
                    if path.parent.name in {"google-news-data-server", "mem0-server"}
                    else RunContextRequired
                )
                with (
                    self.subTest(provider=path.parent.name),
                    self.assertRaises(expected),
                ):
                    runpy.run_path(str(path), run_name="__main__")
        with self.assertRaises(UnsupportedExecutionMode):
            runpy.run_path(str(REPO_ROOT / "utils" / "report.py"), run_name="__main__")

    def test_finnhub_and_duckduckgo_fresh_then_cached_do_not_share_runs(self):
        for provider, file, cls, method, fetch in (
            (
                "finnhub-news-data-server",
                "finnhub_news_service.py",
                "FinnhubNewsService",
                "get_news",
                "company_news",
            ),
            (
                "finnhub-fundamentals-data-server",
                "insider_sentiment_service.py",
                "FinnhubInsiderSentimentService",
                "get_insider_sentiment",
                "stock_insider_sentiment",
            ),
            (
                "finnhub-fundamentals-data-server",
                "insider_transactions_service.py",
                "FinnhubInsiderTransactionsService",
                "get_insider_transactions",
                "stock_insider_transactions",
            ),
        ):
            module = runpy.run_path(
                str(REPO_ROOT / "mcp-servers" / provider / "services" / file)
            )
            constructor = module[cls]
            with patch.object(
                constructor.__init__.__globals__["finnhub"],
                "Client",
                return_value=Mock(),
            ) as factory:
                a = constructor(cache=RunCache.for_run(self.runtime, provider))
                other = new_runtime(Path(self.tmp.name))
                b = constructor(cache=RunCache.for_run(other, provider))
            for service in (a, b):
                getattr(service.client, fetch).return_value = (
                    [] if fetch == "company_news" else {"data": []}
                )
                getattr(service, method)("../../ticker", "2025-08-01", 30)
                getattr(service, method)("../../ticker", "2025-08-01", 30)
            # Each run fetched once even with identical arguments.
            self.assertEqual(getattr(factory.return_value, fetch).call_count, 2)
        provider = "duckduckgo-news-data-server"
        namespace = runpy.run_path(
            str(
                REPO_ROOT
                / "mcp-servers"
                / provider
                / "services"
                / "duckduckgo_news_service.py"
            )
        )
        service = namespace["DuckDuckGoNewsService"](
            cache=RunCache.for_run(self.runtime, provider)
        )
        client = Mock()
        client.news.return_value = []
        with patch.dict(
            service.get_news.__globals__,
            {
                "DDGS": Mock(
                    return_value=Mock(
                        __enter__=Mock(return_value=client),
                        __exit__=Mock(return_value=False),
                    )
                )
            },
        ):
            first = service.get_news("../../query", "2025-08-01", 30)
            cached = service.get_news("../../query", "2025-08-01", 30)
        self.assertEqual(first, cached)
        client.news.assert_called_once()

    def test_yfinance_cookie_timezone_and_isin_roots_are_private(self):
        import yfinance

        from runtime.cache import configure_yfinance

        cache = RunCache.for_run(self.runtime, "yfin-market-data-server")
        with (
            patch.dict(
                os.environ,
                {
                    "INVESTMENT_RUN_ID": self.runtime.context.run_id,
                    "INVESTMENT_CACHE_ROOT": str(cache.context.root),
                },
            ),
            patch.object(yfinance, "set_tz_cache_location") as configure,
        ):
            configure_yfinance(cache)
        configure.assert_called_once_with(str(cache.context.path("vendor", "yfinance")))
        with patch.dict(
            os.environ, {"INVESTMENT_RUN_ID": "", "INVESTMENT_CACHE_ROOT": ""}
        ):
            with self.assertRaises(RunContextRequired):
                configure_yfinance(cache)

    def test_stockstats_both_paths_use_private_atomic_csv(self):
        import pandas as pd

        directory = (
            REPO_ROOT / "mcp-servers" / "stockstats-market-data-server" / "services"
        )
        spec = importlib.util.spec_from_file_location(
            "stockstats_fixture",
            directory / "__init__.py",
            submodule_search_locations=[str(directory)],
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"stockstats_fixture": module}):
            spec.loader.exec_module(module)
            cls = module.StockstatsService
            cache = RunCache.for_run(self.runtime, "stockstats-market-data-server")
            frame = pd.DataFrame(
                {
                    "Open": [10.0, 11.0, 12.0],
                    "High": [11.0, 12.0, 13.0],
                    "Low": [9.0, 10.0, 11.0],
                    "Close": [10.0, 11.0, 12.0],
                    "Volume": [100, 200, 300],
                },
                index=pd.date_range("2025-07-29", periods=3, name="Date"),
            )
            with (
                patch.dict(cls.__init__.__globals__, {"configure_yfinance": Mock()}),
                patch("yfinance.download", return_value=frame) as download,
            ):
                service = cls(cache=cache)
                first = service.get_stock_stats_indicators_window(
                    "AAPL", "close_10_ema", "2025-08-01", 3
                )
                cached = service.get_stock_stats_indicators_window(
                    "AAPL", "close_10_ema", "2025-08-01", 3
                )
            self.assertEqual(first, cached)
            self.assertEqual(
                download.call_count, 2
            )  # window and shared 15-year price history
            self.assertEqual(len(list(cache.context.root.glob("*.csv"))), 2)


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_children_use_only_their_own_cache_and_close(self):
        with TemporaryDirectory() as tmp:
            runtimes = [new_runtime(Path(tmp)), new_runtime(Path(tmp))]
            script = Path(tmp) / "fake_mcp.py"
            script.write_text(
                "import os\nfrom mcp.server.fastmcp import FastMCP\nfrom runtime.cache import RunCache\n"
                "cache=RunCache.for_provider('finnhub-news-data-server')\nmcp=FastMCP('offline')\n"
                "@mcp.tool()\ndef read_cached(query: str) -> str:\n"
                " key=cache.key('fake',{'query':query}); data=cache.read_json(key)\n"
                " if data is None: data={'data':[os.environ['FAKE_VALUE']]}; cache.write_json(key,data)\n"
                " return data['data'][0]\nmcp.run()\n",
                encoding="utf-8",
            )
            clients = []
            environment = dict(os.environ)
            try:
                for runtime, sentinel in zip(runtimes, ("sentinel-A", "sentinel-B")):
                    parameters = server_parameters(runtime, "finnhub-news-data-server")
                    parameters.command = sys.executable
                    parameters.args = ["-B", str(script)]
                    parameters.env["FAKE_VALUE"] = sentinel
                    with patch(
                        "runtime.mcp.server_parameters", return_value=parameters
                    ):
                        clients.append(start_mcp(runtime, "finnhub-news-data-server"))
                for client, sentinel in zip(clients, ("sentinel-A", "sentinel-B")):
                    for number in range(2):
                        result = client.call_tool_sync(
                            str(number), "read_cached", {"query": "../../same"}
                        )
                        self.assertEqual(result["content"][0]["text"], sentinel)
                await runtimes[0].resources.close()
                result = clients[1].call_tool_sync(
                    "after-other-close", "read_cached", {"query": "../../same"}
                )
                self.assertEqual(result["content"][0]["text"], "sentinel-B")
            finally:
                for runtime in runtimes:
                    self.assertFalse(await runtime.resources.close())
            self.assertEqual(dict(os.environ), environment)
            for client in clients:
                self.assertFalse(client._is_session_active())

    async def test_partial_mcp_start_is_registered_before_failure(self):
        with TemporaryDirectory() as tmp:
            runtime = new_runtime(Path(tmp))
            first, second = Mock(), Mock()
            second.start.side_effect = RuntimeError("partial startup")
            with patch("runtime.mcp.MCPClient", side_effect=[first, second]):
                start_mcp(runtime, "finnhub-news-data-server")
                with self.assertRaises(RuntimeError):
                    start_mcp(runtime, "reddit-news-data-server")
            self.assertFalse(await runtime.resources.close())
            first.stop.assert_called_once_with(None, None, None)
            second.stop.assert_called_once_with(None, None, None)

    async def test_partial_second_start_fails_run_without_closing_other_run(self):
        from runtime.context import RunConfig
        from runtime.errors import RunExecutionError
        from runtime.lifecycle import create_run

        with TemporaryDirectory() as tmp:
            other_runtime = new_runtime(Path(tmp))
            failing_runtime = create_run(
                RunConfig("AAPL", "2025-08-01", output_root=Path(tmp))
            )
            other, first, partial = Mock(), Mock(), Mock()
            partial.start.side_effect = RuntimeError("Partial second start")
            order = []
            first.stop.side_effect = lambda *args: order.append("first")
            partial.stop.side_effect = lambda *args: order.append("partial")

            def factory(*, runtime):
                start_mcp(runtime, "finnhub-news-data-server")
                start_mcp(runtime, "reddit-news-data-server")
                raise AssertionError("Construction must fail before invocation")

            with patch("runtime.mcp.MCPClient", side_effect=[other, first, partial]):
                start_mcp(other_runtime, "finnhub-news-data-server")
                try:
                    with self.assertRaises(RunExecutionError) as caught:
                        await failing_runtime.execute(
                            factory, "Analyze", "investment_manager_report"
                        )
                    self.assertEqual(caught.exception.status, "FAILED")
                    self.assertEqual(
                        failing_runtime.store.inspect()["status"], "FAILED"
                    )
                    self.assertEqual(order, ["partial", "first"])
                    other.stop.assert_not_called()
                    other.list_tools_sync()
                finally:
                    await other_runtime.resources.close()
                other.stop.assert_called_once_with(None, None, None)


if __name__ == "__main__":
    unittest.main()
