"""Run-bound compatibility adapter; never import Mem0 in the parent process."""

from runtime.agent import require_runtime
from runtime.errors import RunContextMismatch


class MemoryService:
    def __new__(cls, *, runtime, agent_id="bull_researcher"):
        require_runtime(runtime)
        if agent_id != "bull_researcher":
            raise RunContextMismatch("Memory adapter belongs to another agent")
        return runtime.memory_for(agent_id)


if __name__ == "__main__":
    from agents.researchers.bull.agent import BullResearcher
    from runtime.examples import run_example

    run_example(BullResearcher, "bull_researcher_report")
