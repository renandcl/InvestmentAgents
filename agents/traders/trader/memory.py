"""Run-bound compatibility adapter; never import Mem0 in the parent process."""

from runtime.agent import require_runtime
from runtime.errors import RunContextMismatch


class MemoryService:
    def __new__(cls, *, runtime, agent_id="trader"):
        require_runtime(runtime)
        if agent_id != "trader":
            raise RunContextMismatch("Memory adapter belongs to another agent")
        return runtime.memory_for(agent_id)


if __name__ == "__main__":
    from agents.traders.trader.agent import Trader
    from runtime.examples import run_example

    run_example(Trader, "trader_report")
