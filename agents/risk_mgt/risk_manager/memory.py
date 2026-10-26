"""Run-bound compatibility adapter; never import Mem0 in the parent process."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.risk_mgt.risk_manager.agent import RiskManager
from runtime.agent import require_runtime
from runtime.errors import RunContextMismatch
from runtime.examples import run_example

if TYPE_CHECKING:
    from runtime.lifecycle import RunRuntime


class MemoryService:
    def __new__(
        cls, *, runtime: RunRuntime, agent_id: str = "risk_manager"
    ) -> MemoryService:
        require_runtime(runtime)
        if agent_id != "risk_manager":
            raise RunContextMismatch("Memory adapter belongs to another agent")
        return runtime.memory_for(agent_id)


if __name__ == "__main__":
    run_example(RiskManager, "risk_manager_report")
