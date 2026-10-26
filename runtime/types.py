"""Store values contain snapshots, never open connections or ambient context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from strands import Agent

    from runtime.lifecycle import RunRuntime


class AgentFactory(Protocol):
    def __call__(self, *, runtime: RunRuntime) -> Agent: ...


class ArtifactContext(Protocol):
    def path(self, *parts: str) -> Path: ...


class MemoryService(Protocol):
    """Run-scoped operations; Mem0 owns the dynamic result record schema."""

    def search_memories(
        self, current_situation: str, ticker: str, n_matches: int = 2
    ) -> dict[str, Any]: ...

    def get_memories(self) -> dict[str, Any]: ...

    def add_memory(self, memory: str, ticker: str) -> Any: ...


@dataclass(frozen=True)
class StateSnapshot:
    run_id: str
    values: dict[str, Any]
    revisions: dict[str, int]
    sequence: int


@dataclass(frozen=True)
class WriteReceipt:
    operation_id: str
    revisions: dict[str, int]
    event_sequence: int
    duplicate: bool = False


@dataclass(frozen=True)
class DebateHandle:
    run_id: str
    manager_id: str
    manager_invocation_id: str
    debate_id: str
    generation: int


@dataclass(frozen=True)
class DebateStart:
    handle: DebateHandle
    snapshot: StateSnapshot
    receipt: WriteReceipt


@dataclass(frozen=True)
class Contribution:
    report: str
    invocation_id: str
    operation_id: str


@dataclass(frozen=True)
class RoundReceipt:
    generation: int
    round_number: int
    receipt: WriteReceipt

    @property
    def duplicate(self) -> bool:
        return self.receipt.duplicate


@dataclass(frozen=True)
class ArtifactRecord:
    relative_path: str
    kind: str
    sha256: str
    byte_length: int
    state_sequence: int


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    run_root: Path
    database_path: Path
    report_path: Path | None = None
    state_path: Path | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
