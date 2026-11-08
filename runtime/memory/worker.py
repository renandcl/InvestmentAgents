"""Private child process: scope vendor import-time persistence before importing Mem0."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

from agents.hooks.specs import AGENT_SPECS
from runtime.core.context import contained, validate_run_id
from runtime.core.errors import RunContextMismatch
from runtime.memory.client import memory_config
from runtime.memory.models import MemoryRecord, MemorySnapshot
from runtime.memory.snapshots import (
    MEMORY_LIMIT,
    MEMORY_VERSION,
    SEARCH_CANDIDATES,
    MemoryDirectory,
    rank_memories,
    unique_records,
)
from runtime.store.artifacts import atomic_write


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
    analysis_date = None
    filters = {"user_id": run_id, "agent_id": agent_id}
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                method = request["method"]
                if method == "initialize" and memory is None:
                    analysis_date = request["analysis_date"]
                    if request.get("persistent"):
                        seed = MemorySnapshot.model_validate_json(
                            contained(memory_root, "seed.json").read_bytes()
                        )
                        if (
                            seed.version != MEMORY_VERSION
                            or seed.run_id != run_id
                            or seed.agent_id != agent_id
                            or seed.analysis_date.isoformat() != analysis_date
                        ):
                            raise RunContextMismatch("Invalid persistent memory seed")
                    # Mem0 has import-time persistence side effects. Import only
                    # after validating the private worker environment above.
                    from mem0 import Memory

                    memory = Memory.from_config(memory_config(memory_root))
                    if seed is not None:
                        for record in seed.memories:
                            memory.add(
                                record.memory,
                                **filters,
                                metadata={
                                    "analysis_date": record.analysis_date.isoformat()
                                },
                                infer=False,
                            )
                    result = None
                elif method == "add":
                    result = memory.add(
                        request["memory"],
                        **filters,
                        metadata={"analysis_date": analysis_date},
                        infer=True,
                    )
                elif method == "search":
                    candidates = memory.search(
                        request["query"],
                        filters=dict(filters),
                        top_k=SEARCH_CANDIDATES,
                    )["results"]
                    result = {
                        "results": rank_memories(
                            candidates, analysis_date, request["top_k"]
                        )
                    }
                elif method == "get_all":
                    result = memory.get_all(filters=dict(filters))
                else:
                    raise ValueError("Unsupported memory operation")
                if seed is not None and method in {"initialize", "add"}:
                    records = memory.get_all(filters=dict(filters), top_k=MEMORY_LIMIT)[
                        "results"
                    ]
                    if len(records) >= MEMORY_LIMIT:
                        raise ValueError("Memory export may be truncated")
                    snapshot = seed.model_copy(
                        update={
                            "memories": unique_records(
                                MemoryRecord(
                                    memory=row["memory"],
                                    analysis_date=row["metadata"]["analysis_date"],
                                )
                                for row in records
                            )
                        }
                    )
                    atomic_write(
                        MemoryDirectory(memory_root),
                        "long_term.json",
                        (snapshot.model_dump_json(indent=2) + "\n").encode("utf-8"),
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
