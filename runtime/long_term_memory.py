"""Read only committed memory snapshots; every writable vector store stays private."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agents.hooks.contracts import ContractError
from runtime.artifacts import atomic_write
from runtime.context import MemoryMode, contained, validate_run_id
from runtime.errors import StateStoreUnavailable
from runtime.types import ArtifactRecord

if TYPE_CHECKING:
    from runtime.lifecycle import RunRuntime

MEMORY_LIMIT = 10_000
MEMORY_VERSION = 1


@dataclass(frozen=True)
class MemoryDirectory:
    root: Path

    def path(self, *parts: str) -> Path:
        return contained(self.root, *parts)


def memory_texts(records: object) -> list[str]:
    if (
        not isinstance(records, list)
        or len(records) >= MEMORY_LIMIT
        or any(not isinstance(text, str) or not text.strip() for text in records)
    ):
        raise ContractError("Invalid or oversized persistent memory snapshot")
    return sorted(set(records))


def load_seeds(runtime: RunRuntime, agent_id: str) -> dict[str, Any]:
    context = runtime.context
    texts: set[str] = set()
    sources: list[dict[str, str]] = []
    candidates: dict[str, list[str]] = {}
    superseded: set[str] = set()
    for root in sorted(context.output_root.iterdir()):
        try:
            validate_run_id(root.name)
        except ContractError:
            continue
        if root.name == context.run_id:
            continue
        root = contained(context.output_root, root.name)
        database = contained(root, "run.sqlite3")
        if not database.is_file():
            continue
        try:
            with closing(
                sqlite3.connect(
                    database.as_uri() + "?mode=ro",
                    uri=True,
                    timeout=runtime.config.busy_timeout,
                )
            ) as db:
                db.row_factory = sqlite3.Row
                row = db.execute(
                    "SELECT identity,config,status,finished_at FROM run WHERE singleton=1"
                ).fetchone()
                if not row or row["status"] != "SUCCEEDED":
                    continue
                identity, config = json.loads(row["identity"]), json.loads(
                    row["config"]
                )
                if not isinstance(identity, dict) or not isinstance(config, dict):
                    raise ContractError("Invalid persistent memory source metadata")
                source_date = identity["current_date"]
                if date.fromisoformat(source_date).isoformat() != source_date:
                    raise ContractError("Invalid persistent memory source date")
                if (
                    config.get("memory_mode") != MemoryMode.PERSISTENT
                    or identity.get("ticker") != context.ticker
                    or identity.get("current_date", "") >= context.current_date
                    or not row["finished_at"]
                    or row["finished_at"] > context.created_at
                ):
                    continue
                if identity.get("run_id") != root.name:
                    raise ContractError("Persistent memory source identity mismatch")
                receipt = db.execute(
                    "SELECT relative_path,sha256,byte_length FROM artifacts WHERE kind=?",
                    (f"memory:{agent_id}",),
                ).fetchone()
                if receipt is None:
                    continue
                expected = f"memory/{agent_id}/long_term.json"
                if receipt["relative_path"] != expected:
                    raise ContractError("Invalid persistent memory artifact path")
                path = contained(root, "memory", agent_id, "long_term.json")
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if len(data) != receipt["byte_length"] or digest != receipt["sha256"]:
                    raise ContractError("Persistent memory artifact checksum mismatch")
                snapshot = json.loads(data)
                if not isinstance(snapshot, dict):
                    raise ContractError("Invalid persistent memory snapshot")
                if any(
                    snapshot.get(key) != value
                    for key, value in {
                        "version": MEMORY_VERSION,
                        "run_id": root.name,
                        "agent_id": agent_id,
                        "ticker": context.ticker,
                        "analysis_date": identity["current_date"],
                    }.items()
                ):
                    raise ContractError("Persistent memory snapshot scope mismatch")
                candidates[root.name] = memory_texts(snapshot.get("memories"))
                ancestors = snapshot.get("sources")
                if not isinstance(ancestors, list) or any(
                    not isinstance(source, dict)
                    or not isinstance(source.get("run_id"), str)
                    or not isinstance(source.get("sha256"), str)
                    for source in ancestors
                ):
                    raise ContractError("Invalid persistent memory lineage")
                superseded.update(source["run_id"] for source in ancestors)
                sources.append({"run_id": root.name, "sha256": digest})
        except sqlite3.OperationalError as error:
            # A sibling can be between exclusive allocation and schema creation.
            if "no such table: run" not in str(error):
                raise StateStoreUnavailable(
                    "Cannot read persistent memory source"
                ) from None
        except sqlite3.Error:
            raise StateStoreUnavailable(
                "Cannot read persistent memory source"
            ) from None
        except (ValueError, KeyError, TypeError, OSError):
            raise ContractError("Cannot validate persistent memory source") from None
    # A descendant may have updated/deleted an inherited fact through Mem0.
    # Merge independent heads, not obsolete ancestor versions of the same store.
    for run_id, records in candidates.items():
        if run_id not in superseded:
            texts.update(records)
    return {
        "version": MEMORY_VERSION,
        "run_id": context.run_id,
        "agent_id": agent_id,
        "ticker": context.ticker,
        "analysis_date": context.current_date,
        "sources": sources,
        "memories": memory_texts(sorted(texts)),
    }


def prepare_seeds(runtime: RunRuntime, agent_id: str) -> None:
    seed = load_seeds(runtime, agent_id)
    root = runtime.context.path("memory", agent_id)
    root.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(seed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write(MemoryDirectory(root), "seed.json", data)


def snapshot_artifacts(runtime: RunRuntime, sequence: int) -> list[ArtifactRecord]:
    if runtime.config.memory_mode != MemoryMode.PERSISTENT:
        return []
    artifacts: list[ArtifactRecord] = []
    for agent_id in sorted(runtime._memories):
        path = runtime.context.path("memory", agent_id, "long_term.json")
        if not path.is_file():
            raise ContractError("Persistent worker did not export its memory snapshot")
        data = path.read_bytes()
        artifacts.append(
            ArtifactRecord(
                f"memory/{agent_id}/long_term.json",
                f"memory:{agent_id}",
                hashlib.sha256(data).hexdigest(),
                len(data),
                sequence,
            )
        )
    return artifacts
