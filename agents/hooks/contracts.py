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
class ToolResultTurnPolicy:
    """Legacy policy: a successful tool-result turn is one round, not a quorum."""

    opening_action: str
    debate_action: str
    final_action: str
    max_rounds: int = 3
    track_history: bool = False

    def advance(
        self, rounds: int, processed: list[str], last_message: dict[str, Any]
    ) -> tuple[int, list[str], str | None]:
        seen = set(processed)
        results = {
            result["toolUseId"]
            for block in last_message.get("content", [])
            if (result := block.get("toolResult"))
            and result.get("status") == "success"
            and result.get("toolUseId")
        }
        action = None
        if results - seen:
            rounds += 1
            action = (
                self.final_action if rounds >= self.max_rounds else self.debate_action
            )
        return rounds, sorted(seen | results), action


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    prompt_path: Path
    inputs: tuple[StateField, ...]
    # (template placeholder, state field); aliases such as date are explicit.
    prompt_bindings: tuple[tuple[str, str], ...]
    output_keys: tuple[str, ...]
    memory: MemoryPolicy | None = None
    workflow: ToolResultTurnPolicy | None = None

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
            computed.update(("debate_rounds", "debate_action"))
            if self.workflow.track_history:
                computed.add("risk_debate_history")
            if self.workflow.max_rounds < 1:
                raise ContractError(f"{self.agent_id}: max_rounds must be positive")
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
