"""Memory adapters and worker scoping are explicit; parent imports stay inert."""

import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from isolation_helpers import new_runtime

from runtime.memory_worker import serve

ROOT = Path(__file__).resolve().parents[1]


class MemoryConfigurationTests(unittest.TestCase):
    def test_memory_queries_use_entity_filters_and_top_k(self):
        with TemporaryDirectory() as tmp:
            runtime = new_runtime(Path(tmp))
            backend = Mock()
            backend.add.return_value = {}
            backend.search.return_value = {"results": []}
            backend.get_all.return_value = {"results": []}
            factory = Mock(return_value=backend)
            requests = [
                {"method": "initialize"},
                {"method": "add", "memory": "example"},
                {"method": "get_all"},
                {"method": "search", "query": "query", "top_k": 3},
            ]
            source = io.StringIO("\n".join(json.dumps(request) for request in requests))
            output = io.StringIO()
            with (
                patch.dict(
                    sys.modules,
                    {
                        "mem0": SimpleNamespace(
                            Memory=SimpleNamespace(from_config=factory)
                        )
                    },
                ),
                patch.dict(
                    os.environ,
                    {
                        "INVESTMENT_RUN_ID": runtime.context.run_id,
                        "MEM0_DIR": str(
                            runtime.context.path("memory", "trader", "vendor")
                        ),
                        "MEM0_TELEMETRY": "false",
                    },
                ),
                patch("sys.stdin", source),
                patch("sys.stdout", output),
            ):
                serve(runtime.context.run_root, "trader")
            self.assertTrue(
                all(json.loads(line)["ok"] for line in output.getvalue().splitlines())
            )
            filters = {"user_id": runtime.context.run_id, "agent_id": "trader"}
            backend.get_all.assert_called_once_with(filters=filters)
            backend.search.assert_called_once_with("query", filters=filters, top_k=3)
            backend.add.assert_called_once_with("example", **filters, infer=True)
            config = factory.call_args.args[0]
            self.assertEqual(
                config["history_db_path"],
                str(runtime.context.path("memory", "trader", "history.sqlite3")),
            )

    def test_all_five_adapters_require_runtime_and_use_its_memory(self):
        paths = list(ROOT.glob("agents/**/memory.py"))
        self.assertEqual(len(paths), 5)
        with TemporaryDirectory() as tmp:
            runtime = new_runtime(Path(tmp))
            for path in paths:
                spec = importlib.util.spec_from_file_location(
                    "memory_service_test", path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with self.assertRaises(TypeError):
                    module.MemoryService()
                with patch.object(
                    runtime, "memory_for", return_value=Mock()
                ) as factory:
                    service = module.MemoryService(runtime=runtime)
                    self.assertIs(service, factory.return_value)
                    factory.assert_called_once()
