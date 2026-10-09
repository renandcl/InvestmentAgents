import os

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.traders.trader.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime


class Trader(Agent):
    def __init__(self, *, runtime):
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_session_manager()
        self._init_hooks()

        super().__init__(
            runtime=self.runtime,
            name="TraderAgent",
            agent_id="trader",
            description="Analyzes market data to make informed and strategic investment plans.",
            system_prompt=self.system_prompt,
            model=self.model,
            session_manager=self.session_manager,
            hooks=self.hooks,
        )

    def _init_system_prompt(self):
        with open(
            os.path.join(os.path.dirname(__file__), "prompt.txt"), "r", encoding="utf-8"
        ) as f:
            self.system_prompt = f.read()

    def _init_model(self):
        settings = self.runtime.config.model_for("TRADERS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_session_manager(self):
        self.session_manager = self.runtime.session_for("trader")

    def _init_hooks(self):
        self.lifecycle_hooks = SharedDocument(
            runtime=self.runtime, memory=self.runtime.memory_for("trader")
        )
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def get_trader_investment_plan_decision(self, message: str) -> AgentResult:
        """Get the trading agent to analyze market data to make an informed and strategic investment plandecision"""
        return await self.invoke_async(message)


if __name__ == "__main__":
    from runtime.examples import run_example

    run_example(Trader, "trader_report")
