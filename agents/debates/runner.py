"""Run local participants against one prior-round snapshot; commit only quorum."""

from copy import deepcopy
from typing import Any
from uuid import uuid4

from agents.debates.state import DebateState, RoundContext
from agents.hooks.contracts import ContractError, DebatePolicy
from agents.hooks.services import extract_report
from runtime.errors import RunContextMismatch
from runtime.types import Contribution, DebateStart

PHASE_TASKS = {
    "opening": "Present your evidence-based opening position. No peer arguments exist yet.",
    "rebuttal": "Rebut the other participants' opening arguments using the accepted history.",
    "clarification": "Address rebuttals, clarify assumptions and state your final position.",
}


class DebateRunner:
    def __init__(self, policy: DebatePolicy, participants: dict[str, Any], store):
        policy.validate()
        if set(participants) != {p.agent_id for p in policy.participants}:
            raise ContractError(
                "Debate runner requires exactly the configured participants"
            )
        for participant_spec in policy.participants:
            participant = participants[participant_spec.agent_id]
            if participant.agent_id != participant_spec.agent_id:
                raise ContractError("Debate participant identity mismatch")
            hook = getattr(participant, "lifecycle_hooks", None)
            if hook is None or hook.spec.output_keys != (participant_spec.report_key,):
                raise ContractError(
                    "Debate participant must have one matching lifecycle contract"
                )
            if (
                hook.store.context != store.context
                or participant.runtime.context != store.context
            ):
                raise RunContextMismatch(
                    "Debate participants must belong to the manager's run"
                )
        self.policy, self.participants, self.store = policy, participants, store

    async def run(self, start: DebateStart, request: str) -> DebateState:
        if start.handle.run_id != self.store.context.run_id:
            raise RunContextMismatch("Foreign debate start")
        state = DebateState(self.policy, start.handle.debate_id)
        snapshot = start.snapshot
        while not state.finished:
            contributions = {}
            for participant_spec in self.policy.participants:
                participant = self.participants[participant_spec.agent_id]
                context = RoundContext(
                    state.debate_id,
                    state.round_number,
                    state.phase,
                    participant_spec.agent_id,
                    deepcopy(snapshot),
                    start.handle.run_id,
                    start.handle.manager_id,
                    start.handle.manager_invocation_id,
                    start.handle.generation,
                    uuid4().hex,
                )
                prompt = (
                    f"Debate round {state.round_number} ({state.phase}). "
                    f"{PHASE_TASKS[state.phase]}\nOriginal request: {request}"
                )
                result = await participant.invoke_async(
                    prompt, invocation_state={"debate_context": context}
                )
                if result.stop_reason not in ("end_turn", "stop_sequence"):
                    raise ContractError(
                        f"{participant_spec.agent_id}: incomplete debate contribution"
                    )
                report = extract_report(result.message, participant_spec.agent_id)
                operation_id = uuid4().hex
                state.accept(
                    state.round_number, participant_spec.agent_id, operation_id, report
                )
                contributions[participant_spec.agent_id] = Contribution(
                    report, context.participant_invocation_id, operation_id
                )
            if not state.round_complete:
                raise ContractError("Debate round is incomplete")
            keys = [p.report_key for p in self.policy.participants] + [
                self.policy.history_key
            ]
            receipt = self.store.commit_round(
                debate_handle=start.handle,
                operation_id=uuid4().hex,
                round_number=state.round_number,
                contributions=contributions,
                expected_revisions={
                    key: snapshot.revisions.get(key, 0) for key in keys
                },
            )
            snapshot = self.store.read_snapshot()
            if not receipt.duplicate:
                for participant_spec in self.policy.participants:
                    participant = self.participants[participant_spec.agent_id]
                    participant.state.set(
                        participant_spec.report_key,
                        state.pending[participant_spec.agent_id],
                    )
                    participant.lifecycle_hooks.store_memory(
                        state.pending[participant_spec.agent_id], snapshot.values
                    )
            state.finish_round()
        return state
