"""Actual Mem0/Chroma worker with deterministic inference and denied networking.

Executed only in test-owned child processes with production run environment.
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch


def main():
    # Import only after RunMemory has installed its private child environment.
    from mem0 import Memory

    from runtime.memory_worker import main as serve

    marker = "sentinel-" + os.environ["INVESTMENT_RUN_ID"] + "-trader"

    class Embeddings:
        def embed(self, text, *args, **kwargs):
            return [1.0] + [0.0] * 767

        def embed_batch(self, texts, *args, **kwargs):
            return [self.embed(text) for text in texts]

    original = Memory.from_config

    def factory(config):
        memory = original(config)
        # Exercise real filters even if foreign records exist in the collection.
        memory.add("foreign-run", user_id="foreign", agent_id="trader", infer=False)
        memory.add(
            "foreign-agent",
            user_id=os.environ["INVESTMENT_RUN_ID"],
            agent_id="bull_researcher",
            infer=False,
        )
        # Force auxiliary entity collection creation and record its configured path.
        entity_store = memory.entity_store
        evidence = {
            "chroma": memory.vector_store.settings.persist_directory,
            "entities": entity_store.settings.persist_directory,
            "history": memory.db.db_path,
            "vendor": os.environ["MEM0_DIR"],
        }
        (Path(os.environ["MEM0_DIR"]) / "probe.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        return memory

    with (
        patch(
            "socket.socket.connect",
            side_effect=AssertionError("Network forbidden in offline memory test"),
        ),
        patch("mem0.memory.main.EmbedderFactory.create", return_value=Embeddings()),
        patch(
            "mem0.memory.main.LlmFactory.create",
            return_value=Mock(
                generate_response=Mock(
                    return_value=json.dumps({"memory": [{"text": marker}]})
                )
            ),
        ),
        patch.object(Memory, "from_config", side_effect=factory),
    ):
        serve()


if __name__ == "__main__":
    main()
