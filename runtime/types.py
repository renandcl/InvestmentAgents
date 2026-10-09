"""Store values contain snapshots, never open connections or ambient context."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    def duplicate(self):
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
