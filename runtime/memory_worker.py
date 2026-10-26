"""Private child process: scope vendor import-time persistence before importing Mem0."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

from agents.hooks.specs import AGENT_SPECS
from runtime.artifacts import atomic_write
from runtime.context import contained, validate_run_id
from runtime.errors import RunContextMismatch
from runtime.long_term_memory import (
    MEMORY_LIMIT,
    MEMORY_VERSION,
    MemoryDirectory,
    memory_texts,
)
from runtime.memory import memory_config


def serve(root: Path | str, agent_id: str) -> None:
    run_id = validate_run_id(os.environ.get("INVESTMENT_RUN_ID"))
    root = Path(root)
    if root.name != run_id or agent_id not in AGENT_SPECS:
        raise RunContextMismatch("Invalid memory worker context")
    memory_root = contained(root, "memory", agent_id)
    expected_vendor = contained(memory_root, "vendor")
    if (
        os.environ.get("MEM0_DIR") != str(expected_vendor)
        or os.environ.get("MEM0_TELEMETRY") != "false"
    ):
        raise RunContextMismatch("Memory worker environment mismatch")
    memory = None
    seed = None
    filters = {"user_id": run_id, "agent_id": agent_id}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                method = request["method"]
                if method == "initialize" and memory is None:
                    if request.get("persistent"):
                        seed = json.loads(
                            contained(memory_root, "seed.json").read_text(
                                encoding="utf-8"
                            )
                        )
                        if (
                            seed.get("version") != MEMORY_VERSION
                            or seed.get("run_id") != run_id
                            or seed.get("agent_id") != agent_id
                            or not isinstance(seed.get("ticker"), str)
                            or not isinstance(seed.get("analysis_date"), str)
                        ):
                            raise RunContextMismatch("Invalid persistent memory seed")
                        memory_texts(seed.get("memories"))
                    # Mem0 has import-time persistence side effects. Import only
                    # after validating the private worker environment above.
                    from mem0 import Memory

                    memory = Memory.from_config(memory_config(memory_root))
                    if seed is not None:
                        for text in seed["memories"]:
                            memory.add(text, **filters, infer=False)
                    result = None
                elif memory is None:
                    raise ValueError("Worker is not initialized")
                elif method == "add":
                    result = memory.add(request["memory"], **filters, infer=True)
                elif method == "search":
                    result = memory.search(
                        request["query"], filters=dict(filters), top_k=request["top_k"]
                    )
                elif method == "get_all":
                    result = memory.get_all(filters=dict(filters))
                else:
                    raise ValueError("Unsupported memory operation")
                if seed is not None and method in {"initialize", "add"}:
                    records = memory.get_all(filters=dict(filters), top_k=MEMORY_LIMIT)[
                        "results"
                    ]
                    snapshot = dict(
                        seed, memories=memory_texts([row["memory"] for row in records])
                    )
                    atomic_write(
                        MemoryDirectory(memory_root),
                        "long_term.json",
                        (
                            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
                        ).encode("utf-8"),
                    )
            response = {"ok": True, "result": result}
        except Exception:
            response = {
                "ok": False
            }  # Never send vendor exception strings or credentials.
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--agent-id", required=True)
    args = parser.parse_args()
    serve(args.run_root, args.agent_id)


if __name__ == "__main__":
    main()
