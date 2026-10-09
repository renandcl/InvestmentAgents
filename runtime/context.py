"""Immutable, host-created identity; no ambient current run or mutable routing."""

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from runtime.errors import (
    InvalidRunConfig,
    RunAlreadyExists,
    UnsafeRunPath,
    UnsupportedExecutionMode,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_GROUPS = (
    "ANALYSTS",
    "RESEARCHERS",
    "TRADERS",
    "RISK_MANAGERS",
    "INVESTMENT_MANAGER",
)


class MemoryMode(StrEnum):
    OFF = "OFF"
    RUN_ONLY = "RUN_ONLY"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_run_id(value):
    try:
        parsed = UUID(value)
        if parsed.version != 4 or parsed.hex != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise InvalidRunConfig("Run ID must be lowercase UUID4 hex") from None
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise InvalidRunConfig("Invalid host identifier")
    return value


def contained(root, *parts):
    root = Path(root)
    if not root.is_absolute():
        raise UnsafeRunPath("Root must be absolute")
    for part in parts:
        if (
            not isinstance(part, str)
            or not part
            or part in {".", ".."}
            or any(char in part for char in "/\\:\x00")
        ):
            raise UnsafeRunPath("Path components must be host-selected names")
    target = root.joinpath(*parts)
    # Detect pre-existing symlink/junction redirects, including a replaced run root.
    if root.resolve() != root or target.resolve() != target:
        raise UnsafeRunPath("Run paths cannot contain filesystem redirects")
    if not target.resolve().is_relative_to(root):
        raise UnsafeRunPath("Path escapes the run root")
    return target


@dataclass(frozen=True)
class ModelSettings:
    group: str
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    model_id: str


def resolve_models(environ=None):
    source = os.environ if environ is None else environ
    return tuple(
        ModelSettings(
            group,
            source.get(f"{group}_BASE_URL") or "http://localhost:11434/v1",
            source.get(f"{group}_API_KEY") or "ollama",
            source.get(f"{group}_MODEL_ID") or "qwen3:8b",
        )
        for group in MODEL_GROUPS
    )


@dataclass(frozen=True)
class RunConfig:
    ticker: str
    current_date: str
    output_root: Path = REPO_ROOT / "data" / "runs"
    memory_mode: MemoryMode = MemoryMode.OFF
    execution_mode: str = "in_process"
    busy_timeout: float = 5.0
    cleanup_timeout: float = 30.0
    models: tuple[ModelSettings, ...] = field(
        default_factory=resolve_models, repr=False
    )

    def __post_init__(self):
        if (
            not isinstance(self.ticker, str)
            or not self.ticker.strip()
            or len(self.ticker) > 128
        ):
            raise InvalidRunConfig(
                "Ticker must be a nonempty string of at most 128 characters"
            )
        try:
            if date.fromisoformat(self.current_date).isoformat() != self.current_date:
                raise ValueError
        except (ValueError, TypeError):
            raise InvalidRunConfig("Date must use YYYY-MM-DD") from None
        if self.execution_mode != "in_process":
            raise UnsupportedExecutionMode(
                "Run isolation currently supports in-process execution only"
            )
        try:
            mode = MemoryMode(self.memory_mode)
        except (ValueError, TypeError):
            raise InvalidRunConfig("Unsupported memory mode") from None
        try:
            root = Path(self.output_root).expanduser().absolute()
        except (TypeError, ValueError):
            raise InvalidRunConfig("Output root must be a local path") from None
        if str(root).startswith(("\\\\", "//")):
            raise InvalidRunConfig("A local filesystem is required")
        if root.resolve() != root:
            raise UnsafeRunPath("Output root cannot contain filesystem redirects")
        if any(
            type(value) not in (int, float)
            for value in (self.busy_timeout, self.cleanup_timeout)
        ) or not (0 < self.busy_timeout <= 60 and 0 < self.cleanup_timeout <= 300):
            raise InvalidRunConfig("Timeouts must be finite and bounded")
        if (
            not isinstance(self.models, tuple)
            or any(not isinstance(model, ModelSettings) for model in self.models)
            or {m.group for m in self.models} != set(MODEL_GROUPS)
            or len(self.models) != len(MODEL_GROUPS)
        ):
            raise InvalidRunConfig("Every model group must be configured exactly once")
        if any(
            not all(
                isinstance(v, str) and v for v in (m.base_url, m.api_key, m.model_id)
            )
            for m in self.models
        ):
            raise InvalidRunConfig("Model settings cannot be empty")
        object.__setattr__(self, "memory_mode", mode)
        object.__setattr__(self, "output_root", root)

    def model_for(self, group):
        return next(model for model in self.models if model.group == group)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    ticker: str
    current_date: str
    created_at: str
    output_root: Path
    run_root: Path
    schema_version: int = 1

    def __post_init__(self):
        validate_run_id(self.run_id)
        if self.run_root != contained(self.output_root, self.run_id):
            raise UnsafeRunPath("Run root does not match identity")

    def path(self, *parts):
        contained(self.output_root, self.run_id)
        return contained(self.run_root, *parts)

    @property
    def database_path(self):
        return self.path("run.sqlite3")


def allocate_context(config, *, id_factory=uuid4):
    # Validate the whole config before even allocating a directory.
    if not isinstance(config, RunConfig):
        raise InvalidRunConfig("RunConfig is required")
    run_id = validate_run_id(id_factory().hex)
    root = contained(config.output_root, run_id)
    config.output_root.mkdir(parents=True, exist_ok=True)
    contained(config.output_root, run_id)
    try:
        root.mkdir(exist_ok=False)
    except FileExistsError:
        raise RunAlreadyExists("Run allocation collision") from None
    return RunContext(
        run_id, config.ticker, config.current_date, utc_now(), config.output_root, root
    )
