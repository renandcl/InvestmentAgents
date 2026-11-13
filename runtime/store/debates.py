"""Fenced debate rounds published as complete quorums."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from agents.debates.state import DebateState
from agents.hooks.contracts import ContractError
from runtime.core.context import identifier
from runtime.core.errors import (
    DuplicateOperationConflict,
    RunContextMismatch,
    StateConflict,
)
from runtime.core.types import (
    Contribution,
    DebateHandle,
    DebateStart,
    RoundReceipt,
    StateSnapshot,
    WriteReceipt,
)
from runtime.store.base import StoreBase, canonical


class DebatesMixin(StoreBase):
    def begin_debate(
        self, *, manager_id: str, manager_invocation_id: str, operation_id: str
    ) -> DebateStart:
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
        debate_handle: DebateHandle,
        operation_id: str,
        round_number: int,
        contributions: Mapping[str, Contribution],
        expected_revisions: Mapping[str, int],
    ) -> RoundReceipt:
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

    def validate_round(
        self,
        *,
        handle: DebateHandle,
        participant_id: str,
        round_number: int,
        phase: str,
        snapshot: StateSnapshot,
    ) -> None:
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

    def end_debate(
        self, *, debate_handle: DebateHandle, outcome: str
    ) -> dict[str, Any]:
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
