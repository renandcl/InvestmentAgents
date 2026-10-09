"""SQLite authority for one run, including fenced complete-round publication."""

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict
from uuid import uuid4

from agents.debates.state import DebateState
from agents.hooks.contracts import ContractError
from agents.hooks.specs import AGENT_SPECS
from runtime.context import identifier, utc_now
from runtime.errors import (
    DuplicateOperationConflict,
    RunContextMismatch,
    RunNotWritable,
    SafeError,
    StateConflict,
    StateStoreUnavailable,
)
from runtime.types import (
    Contribution,
    DebateHandle,
    DebateStart,
    RoundReceipt,
    StateSnapshot,
    WriteReceipt,
)

TERMINAL = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})
SCHEMA = """
CREATE TABLE run (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    identity TEXT NOT NULL, config TEXT NOT NULL, provenance TEXT NOT NULL,
    status TEXT NOT NULL, started_at TEXT, finished_at TEXT,
    primary_error TEXT, cleanup_errors TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE state (
    key TEXT PRIMARY KEY, value TEXT, revision INTEGER NOT NULL CHECK(revision > 0),
    writer TEXT NOT NULL, invocation_id TEXT NOT NULL, operation_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
    kind TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE operations (
    operation_id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL
);
CREATE TABLE debates (
    manager_id TEXT PRIMARY KEY, invocation_id TEXT NOT NULL,
    debate_id TEXT NOT NULL, generation INTEGER NOT NULL,
    outcome TEXT NOT NULL, round_number INTEGER NOT NULL DEFAULT 0,
    opening_sequence INTEGER NOT NULL
);
CREATE TABLE rounds (
    manager_id TEXT NOT NULL, generation INTEGER NOT NULL, round_number INTEGER NOT NULL,
    contributions TEXT NOT NULL, snapshot_sequence INTEGER NOT NULL,
    PRIMARY KEY(manager_id, generation, round_number)
);
CREATE TABLE artifacts (
    kind TEXT PRIMARY KEY, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL,
    byte_length INTEGER NOT NULL, state_sequence INTEGER NOT NULL
);
"""


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


class RunStore:
    def __init__(self, context, *, timeout=5.0):
        self.context = context
        self.timeout = timeout
        if not 0 < timeout <= 60:
            raise ContractError("Store timeout must be bounded")

    def initialize(self, config, provenance):
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
    def _transaction(self, *, write=False):
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

    def _event(self, db, kind, details):
        return db.execute(
            "INSERT INTO events(created_at,kind,details) VALUES(?,?,?)",
            (utc_now(), kind, canonical(details)),
        ).lastrowid

    def _sequence(self, db):
        return db.execute("SELECT COALESCE(MAX(sequence),0) FROM events").fetchone()[0]

    def _running(self, db):
        if db.execute("SELECT status FROM run").fetchone()[0] != "RUNNING":
            raise RunNotWritable("Run is not running")

    def _spec(self, agent_id, *, manager=False):
        if agent_id not in AGENT_SPECS:
            raise ContractError("Unknown agent")
        spec = AGENT_SPECS[agent_id]
        if manager and not spec.workflow:
            raise ContractError("Agent has no debate policy")
        return spec

    def _snapshot(self, db):
        record = db.execute("SELECT identity,status FROM run").fetchone()
        values = json.loads(record["identity"])
        values["status"] = record["status"]
        revisions = {}
        for row in db.execute("SELECT key,value,revision FROM state"):
            revisions[row["key"]] = row["revision"]
            if row["value"] is not None:
                values[row["key"]] = row["value"]
        return StateSnapshot(self.context.run_id, values, revisions, self._sequence(db))

    def read_snapshot(self):
        with self._transaction() as db:
            return self._snapshot(db)

    def inspect(self):
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

    def _replay(self, db, operation_id, payload):
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

    def _record(self, db, operation_id, payload, result):
        db.execute(
            "INSERT INTO operations VALUES(?,?,?)",
            (operation_id, canonical(payload), canonical(result)),
        )

    def _revision(self, db, key):
        row = db.execute("SELECT revision FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else 0

    def _check_revisions(self, db, keys, expected):
        if set(expected) != set(keys) or any(
            type(value) is not int or value < 0 for value in expected.values()
        ):
            raise ContractError(
                "Expected revisions must cover exactly the changed keys"
            )
        if any(self._revision(db, key) != expected[key] for key in keys):
            raise StateConflict("Report revision changed")

    def _write(self, db, key, value, writer, invocation_id, operation_id):
        revision = self._revision(db, key) + 1
        db.execute(
            "INSERT INTO state VALUES(?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value,revision=excluded.revision,writer=excluded.writer,"
            "invocation_id=excluded.invocation_id,operation_id=excluded.operation_id,updated_at=excluded.updated_at",
            (key, value, revision, writer, invocation_id, operation_id, utc_now()),
        )
        return revision

    def _handle(self, db, handle):
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

    def patch_reports(
        self,
        *,
        agent_id,
        invocation_id,
        operation_id,
        changes,
        expected_revisions,
        debate_handle=None,
    ):
        spec = self._spec(agent_id)
        identifier(invocation_id)
        if set(changes) != set(spec.output_keys):
            raise ContractError("Publish the complete declared output set")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in changes.values()
        ):
            raise ContractError("Reports must be nonempty text")
        if len(set(changes.values())) != 1:
            raise ContractError("Output aliases must match")
        payload = {
            "kind": "patch",
            "agent": agent_id,
            "invocation": invocation_id,
            "changes": changes,
            "expected": expected_revisions,
            "handle": asdict(debate_handle) if debate_handle else None,
        }
        with self._transaction(write=True) as db:
            replay = self._replay(db, operation_id, payload)
            if replay is not None:
                return WriteReceipt(**replay, duplicate=True)
            self._running(db)
            if spec.workflow:
                row = self._handle(db, debate_handle)
                if (
                    debate_handle.manager_id != agent_id
                    or debate_handle.manager_invocation_id != invocation_id
                    or row["round_number"] != spec.workflow.max_rounds
                ):
                    raise StateConflict("Synthesis requires its own complete debate")
            else:
                if debate_handle is not None:
                    raise ContractError(
                        "Ordinary reports cannot carry manager authority"
                    )
                for manager in AGENT_SPECS.values():
                    if manager.workflow and any(
                        p.agent_id == agent_id for p in manager.workflow.participants
                    ):
                        active = db.execute(
                            "SELECT outcome FROM debates WHERE manager_id=?",
                            (manager.agent_id,),
                        ).fetchone()
                        if active and active[0] == "active":
                            raise StateConflict(
                                "Active debate participants must stage results"
                            )
            self._check_revisions(db, changes, expected_revisions)
            revisions = {
                key: self._write(db, key, value, agent_id, invocation_id, operation_id)
                for key, value in changes.items()
            }
            sequence = self._event(
                db,
                "reports",
                {
                    "agent_id": agent_id,
                    "invocation_id": invocation_id,
                    "operation_id": operation_id,
                },
            )
            result = {
                "operation_id": operation_id,
                "revisions": revisions,
                "event_sequence": sequence,
            }
            self._record(db, operation_id, payload, result)
            return WriteReceipt(**result)

    def begin_debate(self, *, manager_id, manager_invocation_id, operation_id):
        spec = self._spec(manager_id, manager=True)
        identifier(manager_invocation_id)
        payload = {
            "kind": "begin",
            "manager": manager_id,
            "invocation": manager_invocation_id,
        }
        with self._transaction(write=True) as db:
            replay = self._replay(db, operation_id, payload)
            if replay is not None:
                return DebateStart(
                    DebateHandle(**replay["handle"]),
                    StateSnapshot(**replay["snapshot"]),
                    WriteReceipt(**replay["receipt"], duplicate=True),
                )
            self._running(db)
            previous = db.execute(
                "SELECT * FROM debates WHERE manager_id=?", (manager_id,)
            ).fetchone()
            if previous and previous["outcome"] == "active":
                raise StateConflict("A manager invocation already owns this debate")
            generation = previous["generation"] + 1 if previous else 1
            handle = DebateHandle(
                self.context.run_id,
                manager_id,
                manager_invocation_id,
                uuid4().hex,
                generation,
            )
            keys = (
                *spec.output_keys,
                spec.workflow.history_key,
                *(p.report_key for p in spec.workflow.participants),
            )
            revisions = {
                key: self._write(
                    db, key, None, manager_id, manager_invocation_id, operation_id
                )
                for key in keys
            }
            sequence = self._event(
                db,
                "debate_started",
                {
                    "manager_id": manager_id,
                    "invocation_id": manager_invocation_id,
                    "generation": generation,
                },
            )
            db.execute(
                "INSERT INTO debates VALUES(?,?,?,?,'active',0,?) ON CONFLICT(manager_id) DO UPDATE SET "
                "invocation_id=excluded.invocation_id,debate_id=excluded.debate_id,generation=excluded.generation,"
                "outcome='active',round_number=0,opening_sequence=excluded.opening_sequence",
                (
                    manager_id,
                    manager_invocation_id,
                    handle.debate_id,
                    generation,
                    sequence,
                ),
            )
            snapshot = self._snapshot(db)
            receipt = WriteReceipt(operation_id, revisions, sequence)
            result = {
                "handle": asdict(handle),
                "snapshot": asdict(snapshot),
                "receipt": {
                    k: v for k, v in asdict(receipt).items() if k != "duplicate"
                },
            }
            self._record(db, operation_id, payload, result)
            return DebateStart(handle, snapshot, receipt)

    def commit_round(
        self,
        *,
        debate_handle,
        operation_id,
        round_number,
        contributions,
        expected_revisions,
    ):
        if not isinstance(debate_handle, DebateHandle):
            raise RunContextMismatch("Debate handle is required")
        spec = self._spec(debate_handle.manager_id, manager=True)
        policy = spec.workflow
        if set(contributions) != {p.agent_id for p in policy.participants}:
            raise ContractError("Round publication requires a complete quorum")
        for value in contributions.values():
            if (
                not isinstance(value, Contribution)
                or not isinstance(value.report, str)
                or not value.report.strip()
            ):
                raise ContractError("Invalid contribution")
            identifier(value.invocation_id)
            identifier(value.operation_id)
        if len({value.operation_id for value in contributions.values()}) != len(
            contributions
        ):
            raise ContractError("Contribution operation IDs must be distinct")
        payload = {
            "kind": "round",
            "handle": asdict(debate_handle),
            "round": round_number,
            "contributions": {
                key: asdict(value) for key, value in contributions.items()
            },
            "expected": expected_revisions,
        }
        with self._transaction(write=True) as db:
            replay = self._replay(db, operation_id, payload)
            if replay is not None:
                return RoundReceipt(
                    debate_handle.generation,
                    round_number,
                    WriteReceipt(**replay, duplicate=True),
                )
            self._running(db)
            row = self._handle(db, debate_handle)
            if (
                type(round_number) is not int
                or round_number != row["round_number"] + 1
                or round_number > policy.max_rounds
            ):
                raise StateConflict("Unexpected debate round")
            keys = [p.report_key for p in policy.participants] + [policy.history_key]
            self._check_revisions(db, keys, expected_revisions)
            rounds = db.execute(
                "SELECT contributions FROM rounds WHERE manager_id=? AND generation=? ORDER BY round_number",
                (spec.agent_id, debate_handle.generation),
            ).fetchall()
            state = DebateState(policy, debate_handle.debate_id)
            previous_operation_ids = set()
            for accepted in rounds:
                accepted_values = json.loads(accepted[0])
                previous_operation_ids.update(
                    value["operation_id"] for value in accepted_values.values()
                )
                state.completed.append(
                    {key: value["report"] for key, value in accepted_values.items()}
                )
            if previous_operation_ids.intersection(
                value.operation_id for value in contributions.values()
            ):
                raise DuplicateOperationConflict(
                    "A contribution operation was already committed in another round"
                )
            for participant, value in contributions.items():
                state.accept(
                    round_number, participant, value.operation_id, value.report
                )
            state.finish_round()
            revisions = {}
            for participant in policy.participants:
                value = contributions[participant.agent_id]
                revisions[participant.report_key] = self._write(
                    db,
                    participant.report_key,
                    value.report,
                    participant.agent_id,
                    value.invocation_id,
                    value.operation_id,
                )
            revisions[policy.history_key] = self._write(
                db,
                policy.history_key,
                state.history(),
                spec.agent_id,
                debate_handle.manager_invocation_id,
                operation_id,
            )
            sequence = self._event(
                db,
                "round_committed",
                {
                    "manager_id": spec.agent_id,
                    "generation": debate_handle.generation,
                    "round_number": round_number,
                    "operation_id": operation_id,
                },
            )
            db.execute(
                "INSERT INTO rounds VALUES(?,?,?,?,?)",
                (
                    spec.agent_id,
                    debate_handle.generation,
                    round_number,
                    canonical(payload["contributions"]),
                    sequence,
                ),
            )
            db.execute(
                "UPDATE debates SET round_number=? WHERE manager_id=?",
                (round_number, spec.agent_id),
            )
            result = {
                "operation_id": operation_id,
                "revisions": revisions,
                "event_sequence": sequence,
            }
            self._record(db, operation_id, payload, result)
            return RoundReceipt(
                debate_handle.generation, round_number, WriteReceipt(**result)
            )

    def validate_round(self, *, handle, participant_id, round_number, phase, snapshot):
        spec = self._spec(handle.manager_id, manager=True)
        policy = spec.workflow
        if participant_id not in {p.agent_id for p in policy.participants}:
            raise RunContextMismatch("Participant does not belong to this debate")
        with self._transaction() as db:
            self._running(db)
            row = self._handle(db, handle)
            if (
                type(round_number) is not int
                or not 1 <= round_number <= policy.max_rounds
                or round_number != row["round_number"] + 1
                or phase != policy.phases[round_number - 1]
            ):
                raise StateConflict("Round context is stale")
            if (
                not isinstance(snapshot, StateSnapshot)
                or snapshot.run_id != self.context.run_id
            ):
                raise RunContextMismatch("Foreign round snapshot")
            # The runner may pin unrelated state at opening/previous-round time.
            # Check its generation boundary and every debate-owned key revision/value.
            minimum = row["opening_sequence"]
            if snapshot.sequence < minimum or snapshot.sequence > self._sequence(db):
                raise StateConflict("Snapshot does not belong to this generation")
            current = self._snapshot(db)
            for key in (
                *spec.output_keys,
                policy.history_key,
                *(p.report_key for p in policy.participants),
            ):
                if snapshot.revisions.get(key, 0) != current.revisions.get(
                    key, 0
                ) or snapshot.values.get(key) != current.values.get(key):
                    raise StateConflict("Stale or altered round snapshot")
            if any(
                snapshot.values.get(key) != current.values.get(key)
                for key in ("run_id", "ticker", "current_date")
            ):
                raise RunContextMismatch("Snapshot identity mismatch")

    def end_debate(self, *, debate_handle, outcome):
        if outcome not in {"completed", "aborted"}:
            raise ContractError("Invalid debate outcome")
        with self._transaction(write=True) as db:
            self._running(db)
            # Repeated cleanup is idempotent only for this exact handle/outcome.
            existing = db.execute(
                "SELECT * FROM debates WHERE manager_id=?", (debate_handle.manager_id,)
            ).fetchone()
            if (
                existing
                and debate_handle.run_id == self.context.run_id
                and (
                    existing["debate_id"],
                    existing["generation"],
                    existing["invocation_id"],
                    existing["outcome"],
                )
                == (
                    debate_handle.debate_id,
                    debate_handle.generation,
                    debate_handle.manager_invocation_id,
                    outcome,
                )
            ):
                return dict(existing)
            row = self._handle(db, debate_handle)
            spec = self._spec(debate_handle.manager_id, manager=True)
            if outcome == "completed":
                outputs = list(
                    db.execute(
                        "SELECT key,invocation_id,value FROM state WHERE writer=?",
                        (spec.agent_id,),
                    )
                )
                if row["round_number"] != spec.workflow.max_rounds or not all(
                    any(
                        r["key"] == key
                        and r["invocation_id"] == debate_handle.manager_invocation_id
                        and r["value"] is not None
                        for r in outputs
                    )
                    for key in spec.output_keys
                ):
                    raise StateConflict("Debate has no completed synthesis")
            db.execute(
                "UPDATE debates SET outcome=? WHERE manager_id=?",
                (outcome, spec.agent_id),
            )
            self._event(
                db,
                "debate_ended",
                {
                    "manager_id": spec.agent_id,
                    "generation": debate_handle.generation,
                    "outcome": outcome,
                },
            )
            return dict(
                db.execute(
                    "SELECT * FROM debates WHERE manager_id=?", (spec.agent_id,)
                ).fetchone()
            )

    def transition(
        self, expected_status, next_status, *, error=None, cleanup_errors=()
    ):
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

    def commit_success(self, *, artifacts, required_report_key, expected_sequence):
        if {item.kind for item in artifacts} != {"state", "report"} or len(
            artifacts
        ) != 2:
            raise ContractError("Both final artifacts are required")
        if required_report_key not in {
            key for spec in AGENT_SPECS.values() for key in spec.output_keys
        }:
            raise ContractError("Unknown required report")
        with self._transaction(write=True) as db:
            self._running(db)
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
                expected_name = (
                    "report.md" if item.kind == "report" else "shared_document.json"
                )
                if (
                    item.relative_path != expected_name
                    or item.state_sequence != expected_sequence
                ):
                    raise ContractError("Invalid artifact receipt")
                data = self.context.path(item.relative_path).read_bytes()
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
