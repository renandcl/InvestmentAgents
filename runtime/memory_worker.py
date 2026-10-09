"""Private child process: scope vendor import-time persistence before importing Mem0."""

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

from agents.hooks.specs import AGENT_SPECS
from runtime.context import contained, validate_run_id
from runtime.errors import RunContextMismatch
from runtime.memory import memory_config


def serve(root, agent_id):
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
    filters = {"user_id": run_id, "agent_id": agent_id}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                method = request["method"]
                if method == "initialize" and memory is None:
                    from mem0 import Memory

                    memory = Memory.from_config(memory_config(memory_root))
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
            response = {"ok": True, "result": result}
        except Exception:
            response = {
                "ok": False
            }  # Never send vendor exception strings or credentials.
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--agent-id", required=True)
    args = parser.parse_args()
    serve(args.run_root, args.agent_id)


if __name__ == "__main__":
    main()
