"""Run-bound compatibility adapter; never import Mem0 in the parent process."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.researchers.bear.agent import BearResearcher
from runtime.core.errors import RunContextMismatch
from runtime.execution.agent import require_runtime
from runtime.execution.examples import run_example

if TYPE_CHECKING:
    from runtime.execution.lifecycle import RunRuntime


class MemoryService:
    def __new__(
        cls, *, runtime: RunRuntime, agent_id: str = "bear_researcher"
    ) -> MemoryService:
        require_runtime(runtime)
        if agent_id != "bear_researcher":
            raise RunContextMismatch("Memory adapter belongs to another agent")
        return runtime.memory_for(agent_id)


if __name__ == "__main__":
    run_example(BearResearcher, "bear_researcher_report")
