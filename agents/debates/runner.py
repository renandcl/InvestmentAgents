"""Run local participants and publish only complete rounds."""

from copy import deepcopy
from typing import Any
from uuid import uuid4

from agents.debates.state import DebateState, RoundContext
from agents.hooks.contracts import ContractError, DebatePolicy
from agents.hooks.services import JsonReportStore, extract_report

PHASE_TASKS = {
    "opening": "Present your evidence-based opening position. No peer arguments exist yet.",
    "rebuttal": "Rebut the other participants' opening arguments using the accepted history.",
    "clarification": "Address rebuttals, clarify assumptions and state your final position.",
}


class DebateRunner:
    def __init__(
        self, policy: DebatePolicy, participants: dict[str, Any], store: JsonReportStore
    ):
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
        self.policy = policy
        self.participants = participants
        self.store = store

    async def run(
        self, snapshot: dict[str, Any], request: str, output_keys: tuple[str, ...]
    ) -> DebateState:
        state = DebateState(self.policy, uuid4().hex)
        peer_keys = tuple(p.report_key for p in self.policy.participants)
        reset_keys = peer_keys + output_keys + (self.policy.history_key,)
        self.store.patch({}, remove_keys=reset_keys)
        snapshot = deepcopy(snapshot)
        for key in reset_keys:
            snapshot.pop(key, None)
        snapshot[self.policy.history_key] = state.history()
        while not state.finished:
            for participant_spec in self.policy.participants:
                participant = self.participants[participant_spec.agent_id]
                context = RoundContext(
                    state.debate_id,
                    state.round_number,
                    state.phase,
                    participant_spec.agent_id,
                    deepcopy(snapshot),
                )
                # The snapshot/history owns context; avoid stale conversation messages.
                participant.messages.clear()
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
                state.accept(
                    state.round_number, participant_spec.agent_id, uuid4().hex, report
                )
            if not state.round_complete:
                raise ContractError("Debate round is incomplete")
            changes = {
                p.report_key: state.pending[p.agent_id]
                for p in self.policy.participants
            }
            changes[self.policy.history_key] = state.history(include_pending=True)
            self.store.patch(changes)
            snapshot.update(changes)
            for participant_spec in self.policy.participants:
                participant = self.participants[participant_spec.agent_id]
                participant.state.set(
                    participant_spec.report_key,
                    state.pending[participant_spec.agent_id],
                )
                hook = participant.lifecycle_hooks
                hook.store_memory(state.pending[participant_spec.agent_id], snapshot)
            state.finish_round()
        return state
