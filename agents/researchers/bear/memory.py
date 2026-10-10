"""Run-bound compatibility adapter; never import Mem0 in the parent process."""

from agents.researchers.bear.agent import BearResearcher
from runtime.agent import require_runtime
from runtime.errors import RunContextMismatch
from runtime.examples import run_example


class MemoryService:
    def __new__(cls, *, runtime, agent_id="bear_researcher"):
        require_runtime(runtime)
        if agent_id != "bear_researcher":
            raise RunContextMismatch("Memory adapter belongs to another agent")
        return runtime.memory_for(agent_id)


if __name__ == "__main__":
    run_example(BearResearcher, "bear_researcher_report")
