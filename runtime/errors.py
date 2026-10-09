"""Safe, named runtime failures; persisted diagnostics never include exception text."""

import re
from dataclasses import dataclass

from agents.hooks.contracts import ContractError


class InvalidRunConfig(ContractError):
    pass


class RunAlreadyExists(ContractError):
    pass


class RunContextRequired(ContractError):
    pass


class RunContextMismatch(ContractError):
    pass


class UnsafeRunPath(ContractError):
    pass


class StateConflict(ContractError):
    pass


class DuplicateOperationConflict(StateConflict):
    pass


class RunNotWritable(ContractError):
    pass


class StateStoreUnavailable(RuntimeError):
    pass


class UnsupportedExecutionMode(ContractError):
    pass


class CleanupTimeout(RuntimeError):
    pass


@dataclass(frozen=True)
class SafeError:
    category: str
    stage: str
    agent_id: str | None = None
    invocation_id: str | None = None

    def __post_init__(self):
        if self.agent_id is not None:
            from agents.hooks.specs import AGENT_SPECS

            if self.agent_id not in AGENT_SPECS:
                raise ContractError("Unknown failure owner")
        if self.invocation_id is not None and not re.fullmatch(
            r"[a-f0-9]{32}", self.invocation_id
        ):
            raise ContractError("Invalid failure invocation")
        if self.stage not in {
            "allocation",
            "construction",
            "invocation",
            "cleanup",
            "export",
            "status",
        }:
            raise ContractError("Unknown failure stage")
        if self.category not in {
            "InvalidRunConfig",
            "RunContextMismatch",
            "UnsafeRunPath",
            "StateConflict",
            "DuplicateOperationConflict",
            "RunNotWritable",
            "StateStoreUnavailable",
            "UnsupportedExecutionMode",
            "CleanupTimeout",
            "ContractError",
            "CancelledError",
            "ExecutionFailure",
        }:
            raise ContractError("Unknown safe failure category")

    @classmethod
    def from_exception(cls, error, stage, *, agent_id=None, invocation_id=None):
        category = type(error).__name__
        try:
            return cls(category, stage, agent_id, invocation_id)
        except ContractError:
            return cls("ExecutionFailure", stage, agent_id, invocation_id)


class RunExecutionError(RuntimeError):
    def __init__(self, context, status, error):
        self.run_id = context.run_id
        self.run_root = context.run_root
        self.status = status
        self.error = error
        super().__init__(
            f"Run {self.run_id}: {status} ({error.category}/{error.stage})"
        )
