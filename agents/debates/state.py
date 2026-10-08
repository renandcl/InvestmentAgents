"""Pure state machine; accepted contributions, not tool turns, complete rounds."""

from dataclasses import dataclass, field
from typing import Any

from agents.hooks.contracts import ContractError, DebatePolicy


@dataclass(frozen=True)
class RoundContext:
    debate_id: str
    round_number: int
    phase: str
    participant_id: str
    snapshot: dict[str, Any]


@dataclass
class DebateState:
    policy: DebatePolicy
    debate_id: str
    completed: list[dict[str, str]] = field(default_factory=list)
    pending: dict[str, str] = field(default_factory=dict)
    operations: dict[str, tuple[int, str, str]] = field(default_factory=dict)

    @property
    def round_number(self) -> int:
        return len(self.completed) + 1

    @property
    def phase(self) -> str:
        return "synthesis" if self.finished else self.policy.phases[len(self.completed)]

    @property
    def finished(self) -> bool:
        return len(self.completed) == self.policy.max_rounds

    @property
    def round_complete(self) -> bool:
        return set(self.pending) == {p.agent_id for p in self.policy.participants}

    def accept(
        self, round_number: int, participant_id: str, operation_id: str, report: str
    ) -> bool:
        payload = (round_number, participant_id, report)
        if operation_id in self.operations:
            if self.operations[operation_id] != payload:
                raise ContractError("Conflicting duplicate debate operation")
            return False
        if self.finished or round_number != self.round_number:
            raise ContractError("Contribution belongs to the wrong debate round")
        if participant_id not in {p.agent_id for p in self.policy.participants}:
            raise ContractError("Unknown debate participant")
        if not operation_id or not isinstance(report, str) or not report.strip():
            raise ContractError(
                "Debate contribution requires an operation and nonempty report"
            )
        if participant_id in self.pending:
            raise ContractError("Participant has already contributed to this round")
        self.pending[participant_id] = report
        self.operations[operation_id] = payload
        return True

    def finish_round(self) -> None:
        if self.finished or not self.round_complete:
            raise ContractError(
                "Cannot complete a debate round without all participants"
            )
        self.completed.append(dict(self.pending))
        self.pending.clear()

    def history(self, *, include_pending: bool = False) -> str:
        rounds = self.completed + ([self.pending] if include_pending else [])
        blocks = []
        for number, reports in enumerate(rounds, 1):
            lines = [f"Round {number} ({self.policy.phases[number - 1]})"]
            # Canonical order keeps transcripts independent of execution order.
            for agent_id in sorted(reports):
                lines.append(f"{agent_id}:\n{reports[agent_id]}")
            blocks.append("\n\n".join(lines))
        return "\n\n".join(blocks) or "No debate history yet."
