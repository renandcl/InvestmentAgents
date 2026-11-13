"""Report publication with expected revisions and receipts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict

from agents.hooks.contracts import ContractError
from agents.hooks.specs import AGENT_SPECS
from runtime.core.context import identifier
from runtime.core.errors import StateConflict
from runtime.core.types import (
    DebateHandle,
    WriteReceipt,
)
from runtime.store.base import StoreBase


class ReportsMixin(StoreBase):
    def patch_reports(
        self,
        *,
        agent_id: str,
        invocation_id: str,
        operation_id: str,
        changes: Mapping[str, str],
        expected_revisions: Mapping[str, int],
        debate_handle: DebateHandle | None = None,
    ) -> WriteReceipt:
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
