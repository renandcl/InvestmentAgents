import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


class MemoryConfigurationTests(unittest.TestCase):
    def test_memory_queries_use_entity_filters_and_top_k(self):
        paths = list(ROOT.glob("agents/**/memory.py")) + [
            ROOT / "mcp-servers/mem0-server/services/mem0_service.py"
        ]
        for path in paths:
            with self.subTest(service=str(path.relative_to(ROOT))):
                spec = importlib.util.spec_from_file_location(
                    "memory_service_test", path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                service = module.MemoryService.__new__(module.MemoryService)
                service.agent_id = "test-agent"
                service.memory = Mock()
                service.get_memories()
                service.memory.get_all.assert_called_once_with(
                    filters={"agent_id": "test-agent"}
                )
                service.search_memories("query", "AAPL", 3)
                service.memory.search.assert_called_once_with(
                    "query",
                    filters={"user_id": "AAPL", "agent_id": "test-agent"},
                    top_k=3,
                )
