"""Immutable contracts; workflow policy is independent of Strands and prompts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """An agent contract, input or output is invalid."""


@dataclass(frozen=True)
class StateField:
    name: str
    source: str | None = None
    default: str | None = None
    required: bool = False
    refresh: bool = False

    @property
    def source_key(self) -> str:
        return self.source or self.name

    def resolve(self, snapshot: dict[str, Any], agent_id: str) -> Any:
        value = snapshot.get(self.source_key)
        if self.required and (not isinstance(value, str) or not value.strip()):
            raise ContractError(
                f"{agent_id}: required input {self.source_key!r} missing"
            )
        return self.default if value is None else value


@dataclass(frozen=True)
class MemoryPolicy:
    query_fields: tuple[tuple[str, str], ...]
    store_label: str
    empty_text: str = "No relevant past memories found."
    n_matches: int = 2


@dataclass(frozen=True)
class ParticipantSpec:
    agent_id: str
    report_key: str


@dataclass(frozen=True)
class DebatePolicy:
    participants: tuple[ParticipantSpec, ...]
    history_key: str
    final_action: str
    phases: tuple[str, ...] = ("opening", "rebuttal", "clarification")

    @property
    def max_rounds(self) -> int:
        return len(self.phases)

    def validate(self) -> None:
        ids = [participant.agent_id for participant in self.participants]
        keys = [participant.report_key for participant in self.participants]
        if (
            not ids
            or len(ids) != len(set(ids))
            or len(keys) != len(set(keys))
            or any(key != f"{agent_id}_report" for agent_id, key in zip(ids, keys))
            or self.phases != ("opening", "rebuttal", "clarification")
        ):
            raise ContractError("Invalid debate participants or phases")


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    prompt_path: Path
    inputs: tuple[StateField, ...]
    # (template placeholder, state field); aliases such as date are explicit.
    prompt_bindings: tuple[tuple[str, str], ...]
    output_keys: tuple[str, ...]
    memory: MemoryPolicy | None = None
    workflow: DebatePolicy | None = None

    def validate(self) -> None:
        names = [field.name for field in self.inputs]
        placeholders = [name for name, _ in self.prompt_bindings]
        computed = set()
        if self.memory:
            computed.add("past_memories")
            if self.memory.n_matches < 1:
                raise ContractError(
                    f"{self.agent_id}: memory n_matches must be positive"
                )
        if self.workflow:
            self.workflow.validate()
            computed.update(("debate_rounds", "debate_action", "debate_phase"))
            if self.workflow.history_key not in names:
                raise ContractError(f"{self.agent_id}: undeclared debate history input")
        available = set(names) | computed
        if (
            not self.agent_id
            or len(names) != len(set(names))
            or len(placeholders) != len(set(placeholders))
            or set(names) & computed
            or not self.output_keys
            or len(self.output_keys) != len(set(self.output_keys))
            or self.output_keys[0] != f"{self.agent_id}_report"
            or not all(key.isidentifier() for key in self.output_keys)
        ):
            raise ContractError(
                f"{self.agent_id}: invalid or duplicate contract fields"
            )
        if any(source not in available for _, source in self.prompt_bindings):
            raise ContractError(
                f"{self.agent_id}: prompt binding has undeclared source"
            )
        if self.memory:
            input_sources = {field.source_key for field in self.inputs}
            if any(key not in input_sources for _, key in self.memory.query_fields):
                raise ContractError(
                    f"{self.agent_id}: memory query has undeclared input"
                )
