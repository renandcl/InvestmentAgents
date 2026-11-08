"""SQLite authority for one run: schema, transactions, status and success."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from agents.hooks.contracts import ContractError
from agents.hooks.specs import AGENT_SPECS
from runtime.core.context import identifier, utc_now
from runtime.core.errors import (
    DuplicateOperationConflict,
    RunContextMismatch,
    RunNotWritable,
    SafeError,
    StateConflict,
    StateStoreUnavailable,
)
from runtime.core.types import (
    DebateHandle,
    StateSnapshot,
)

if TYPE_CHECKING:
    from agents.hooks.contracts import AgentSpec
    from runtime.core.context import RunConfig, RunContext
    from runtime.core.types import ArtifactRecord

TERMINAL = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})
SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


class StoreBase:
    def __init__(self, context: RunContext, *, timeout: float = 5.0) -> None:
        self.context = context
        self.timeout = timeout
        if not 0 < timeout <= 60:
            raise ContractError("Store timeout must be bounded")

    def initialize(self, config: RunConfig, provenance: Mapping[str, Any]) -> None:
        path = self.context.database_path
        # Exclusive placeholder: initialization must never overwrite another database.
        with path.open("xb"):
            pass
        identity = {
            "schema_version": self.context.schema_version,
            "run_id": self.context.run_id,
            "ticker": self.context.ticker,
            "current_date": self.context.current_date,
            "created_at": self.context.created_at,
        }
        safe_config = {
            "memory_mode": config.memory_mode.value,
            "execution_mode": config.execution_mode,
            "memory_request_timeout": config.memory_request_timeout,
            "model_ids": {m.group: m.model_id for m in config.models},
        }
        # Provenance is constructed by the runtime, not copied from environment/config.
        if set(provenance) != {
            "code_revision",
            "dirty",
            "lockfile_hash",
            "prompt_hashes",
        }:
            raise ContractError("Unexpected provenance fields")
        try:
            with closing(sqlite3.connect(path, timeout=self.timeout)) as db, db:
                db.execute("PRAGMA journal_mode=DELETE")
                db.execute("PRAGMA synchronous=FULL")
                db.executescript(SCHEMA)
                db.execute(
                    "INSERT INTO run(singleton,identity,config,provenance,status) VALUES(1,?,?,?,'CREATED')",
                    (
                        canonical(identity),
                        canonical(safe_config),
                        canonical(provenance),
                    ),
                )
                self._event(db, "created", {})
        except sqlite3.Error:
            raise StateStoreUnavailable("Run initialization failed") from None

    @contextmanager
    def _transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = None
        try:
            # mode=rw avoids silently creating an empty database after a path error.
            db = sqlite3.connect(
                self.context.database_path.as_uri() + "?mode=rw",
                uri=True,
                timeout=self.timeout,
            )
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            record = db.execute("SELECT identity FROM run WHERE singleton=1").fetchone()
            expected_identity = {
                "run_id": self.context.run_id,
                "schema_version": self.context.schema_version,
                "ticker": self.context.ticker,
                "current_date": self.context.current_date,
                "created_at": self.context.created_at,
            }
            if not record or json.loads(record[0]) != expected_identity:
                raise RunContextMismatch("Store identity mismatch")
            yield db
            db.commit()
        except sqlite3.Error:
            if db is not None:
                db.rollback()
            raise StateStoreUnavailable("Run store operation failed") from None
        except BaseException:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    def _event(
        self, db: sqlite3.Connection, kind: str, details: Mapping[str, Any]
    ) -> int:
        return cast(
            int,
            db.execute(
                "INSERT INTO events(created_at,kind,details) VALUES(?,?,?)",
                (utc_now(), kind, canonical(details)),
            ).lastrowid,
        )

    def _sequence(self, db: sqlite3.Connection) -> int:
        return db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]

    def _running(self, db: sqlite3.Connection) -> None:
        if db.execute("SELECT status FROM run").fetchone()[0] != "RUNNING":
            raise RunNotWritable("Run is not running")

    def _spec(self, agent_id: str, *, manager: bool = False) -> AgentSpec:
        if agent_id not in AGENT_SPECS:
            raise ContractError("Unknown agent")
        spec = AGENT_SPECS[agent_id]
        if manager and not spec.workflow:
            raise ContractError("Agent has no debate policy")
        return spec

    def _snapshot(self, db: sqlite3.Connection) -> StateSnapshot:
        record = db.execute("SELECT identity,status FROM run").fetchone()
        values = json.loads(record["identity"])
        values["status"] = record["status"]
        revisions = {}
        for row in db.execute("SELECT key,value,revision FROM state"):
            revisions[row["key"]] = row["revision"]
            if row["value"] is not None:
                values[row["key"]] = row["value"]
        return StateSnapshot(self.context.run_id, values, revisions, self._sequence(db))

    def read_snapshot(self) -> StateSnapshot:
        with self._transaction() as db:
            return self._snapshot(db)

    def inspect(self) -> dict[str, Any]:
        with self._transaction() as db:
            record = dict(db.execute("SELECT * FROM run").fetchone())
            record.pop("singleton")
            for key in (
                "identity",
                "config",
                "provenance",
                "primary_error",
                "cleanup_errors",
            ):
                record[key] = (
                    json.loads(record[key]) if record[key] is not None else None
                )
            record["artifacts"] = [
                dict(row) for row in db.execute("SELECT * FROM artifacts ORDER BY kind")
            ]
            record["sequence"] = self._sequence(db)
            return record

    def status(self) -> str:
        """Read durable lifecycle status without decoding inspection metadata."""
        with self._transaction() as db:
            return db.execute("SELECT status FROM run WHERE singleton=1").fetchone()[0]

    def _replay(
        self, db: sqlite3.Connection, operation_id: str, payload: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        identifier(operation_id)
        row = db.execute(
            "SELECT payload,result FROM operations WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        if row is None:
            return None
        if row["payload"] != canonical(payload):
            raise DuplicateOperationConflict(
                "Operation ID was used with a different payload"
            )
        return json.loads(row["result"])

    def _record(
        self,
        db: sqlite3.Connection,
        operation_id: str,
        payload: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> None:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?)",
            (operation_id, canonical(payload), canonical(result)),
        )

    def _revision(self, db: sqlite3.Connection, key: str) -> int:
        row = db.execute("SELECT revision FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else 0

    def _check_revisions(
        self, db: sqlite3.Connection, keys: Iterable[str], expected: Mapping[str, int]
    ) -> None:
        if set(expected) != set(keys) or any(
            type(value) is not int or value < 0 for value in expected.values()
        ):
            raise ContractError(
                "Expected revisions must cover exactly the changed keys"
            )
        if any(self._revision(db, key) != expected[key] for key in keys):
            raise StateConflict("Report revision changed")

    def _write(
        self,
        db: sqlite3.Connection,
        key: str,
        value: str | None,
        writer: str,
        invocation_id: str,
        operation_id: str,
    ) -> int:
        revision = self._revision(db, key) + 1
        db.execute(
            "INSERT INTO state VALUES(?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value,revision=excluded.revision,writer=excluded.writer,"
            "invocation_id=excluded.invocation_id,operation_id=excluded.operation_id,updated_at=excluded.updated_at",
            (key, value, revision, writer, invocation_id, operation_id, utc_now()),
        )
        return revision

    def _handle(self, db: sqlite3.Connection, handle: DebateHandle) -> sqlite3.Row:
        if not isinstance(handle, DebateHandle) or handle.run_id != self.context.run_id:
            raise RunContextMismatch("Foreign debate handle")
        row = db.execute(
            "SELECT * FROM debates WHERE manager_id=?", (handle.manager_id,)
        ).fetchone()
        if not row or (
            row["invocation_id"],
            row["debate_id"],
            row["generation"],
            row["outcome"],
        ) != (
            handle.manager_invocation_id,
            handle.debate_id,
            handle.generation,
            "active",
        ):
            raise StateConflict("Debate generation is not active")
        return row

    def transition(
        self,
        expected_status: str,
        next_status: str,
        *,
        error: SafeError | None = None,
        cleanup_errors: Sequence[SafeError] = (),
    ) -> dict[str, Any]:
        allowed = {
            ("CREATED", "RUNNING"),
            ("CREATED", "FAILED"),
            ("CREATED", "CANCELLED"),
            ("RUNNING", "FAILED"),
            ("RUNNING", "CANCELLED"),
        }
        if (expected_status, next_status) not in allowed:
            raise RunNotWritable(
                "Invalid lifecycle transition; success requires artifact commit"
            )
        if (
            error is not None
            and not isinstance(error, SafeError)
            or any(not isinstance(item, SafeError) for item in cleanup_errors)
        ):
            raise ContractError("Only allowlisted errors can be persisted")
        with self._transaction(write=True) as db:
            current = db.execute("SELECT status FROM run").fetchone()[0]
            if current != expected_status:
                raise RunNotWritable("Run status has already changed")
            now = utc_now()
            db.execute(
                "UPDATE run SET status=?,started_at=COALESCE(started_at,?),finished_at=?,primary_error=?,cleanup_errors=?",
                (
                    next_status,
                    now if next_status == "RUNNING" else None,
                    now if next_status in TERMINAL else None,
                    canonical(asdict(error)) if error else None,
                    canonical([asdict(item) for item in cleanup_errors]),
                ),
            )
            if next_status in TERMINAL:
                db.execute(
                    "UPDATE debates SET outcome='aborted' WHERE outcome='active'"
                )
            self._event(db, "status", {"status": next_status})
        return self.inspect()

    def commit_success(
        self,
        *,
        artifacts: Sequence[ArtifactRecord],
        required_report_key: str,
        expected_sequence: int,
    ) -> dict[str, Any]:
        kinds = {item.kind for item in artifacts}
        if not {"state", "report"} <= kinds or len(kinds) != len(artifacts):
            raise ContractError("Both final artifacts are required")
        expected_paths = {"state": "shared_document.json", "report": "report.md"}
        if required_report_key not in {
            key for spec in AGENT_SPECS.values() for key in spec.output_keys
        }:
            raise ContractError("Unknown required report")
        with self._transaction(write=True) as db:
            self._running(db)
            config = json.loads(db.execute("SELECT config FROM run").fetchone()[0])
            if config["memory_mode"] == "PERSISTENT":
                expected_paths.update(
                    {
                        f"memory:{agent_id}": f"memory/{agent_id}/long_term.json"
                        for agent_id, spec in AGENT_SPECS.items()
                        if spec.memory
                    }
                )
            if not kinds <= expected_paths.keys():
                raise ContractError("Unknown final artifact kind")
            if self._sequence(db) != expected_sequence:
                raise StateConflict("State changed during export")
            if db.execute("SELECT 1 FROM debates WHERE outcome='active'").fetchone():
                raise StateConflict("A debate still owns active work")
            report = db.execute(
                "SELECT value FROM state WHERE key=?", (required_report_key,)
            ).fetchone()
            if not report or not report[0]:
                raise ContractError("Required root report is absent")
            for item in artifacts:
                expected_name = expected_paths[item.kind]
                if (
                    item.relative_path != expected_name
                    or item.state_sequence != expected_sequence
                ):
                    raise ContractError("Invalid artifact receipt")
                data = self.context.path(*item.relative_path.split("/")).read_bytes()
                if (
                    len(data) != item.byte_length
                    or hashlib.sha256(data).hexdigest() != item.sha256
                ):
                    raise StateConflict("Artifact content changed before commit")
                db.execute(
                    "INSERT INTO artifacts VALUES(?,?,?,?,?)",
                    (
                        item.kind,
                        item.relative_path,
                        item.sha256,
                        item.byte_length,
                        item.state_sequence,
                    ),
                )
            db.execute("UPDATE run SET status='SUCCEEDED',finished_at=?", (utc_now(),))
            self._event(db, "status", {"status": "SUCCEEDED"})
        return self.inspect()
