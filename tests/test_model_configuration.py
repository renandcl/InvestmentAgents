"""Model configuration must accept the blank values in .env.example."""

import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from strands import Agent

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("ANALYSTS", "RESEARCHERS", "TRADERS", "RISK_MANAGERS", "INVESTMENT_MANAGER")


class ModelConfigurationTests(unittest.TestCase):
    def check_configuration(
        self, settings, expected_base, expected_key, expected_model
    ):
        paths = sorted((ROOT / "agents").rglob("agent.py")) + sorted(
            (ROOT / "agents").rglob("a2a_agent.py")
        )
        with patch.dict(os.environ, settings):
            for path in paths:
                name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
                module = importlib.import_module(name)
                classes = [
                    cls
                    for cls in vars(module).values()
                    if isinstance(cls, type)
                    and issubclass(cls, Agent)
                    and cls.__module__ == name
                ]
                self.assertEqual(len(classes), 1)
                with (
                    self.subTest(agent=name),
                    patch.object(module, "OpenAIModel") as model,
                ):
                    instance = classes[0].__new__(classes[0])
                    instance._init_model()
                    kwargs = model.call_args.kwargs
                    self.assertEqual(kwargs["client_args"]["base_url"], expected_base)
                    self.assertEqual(kwargs["client_args"]["api_key"], expected_key)
                    self.assertEqual(kwargs["model_id"], expected_model)

    def test_blank_environment_values_use_ollama_defaults(self):
        settings = {
            group + "_" + suffix: ""
            for group in GROUPS
            for suffix in ("BASE_URL", "API_KEY", "MODEL_ID")
        }
        self.check_configuration(
            settings, "http://localhost:11434/v1", "ollama", "qwen3:8b"
        )

    def test_explicit_environment_values_are_preserved(self):
        values = {
            "BASE_URL": "http://example.invalid/v1",
            "API_KEY": "configured",  # pragma: allowlist secret - dummy test value
            "MODEL_ID": "custom-model",
        }
        settings = {
            group + "_" + suffix: value
            for group in GROUPS
            for suffix, value in values.items()
        }
        self.check_configuration(
            settings, values["BASE_URL"], values["API_KEY"], values["MODEL_ID"]
        )


if __name__ == "__main__":
    unittest.main()
