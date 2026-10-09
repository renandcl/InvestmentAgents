import logging
import os

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.analysts.analysts_coordinator.hook import SharedDocument
from agents.analysts.fundamentals_analyst.agent import FundamentalsAnalyst
from agents.analysts.market_analyst.agent import MarketAnalyst
from agents.analysts.news_analyst.agent import NewsAnalyst
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class AnalystCoordinator(Agent):
    def __init__(self, *, runtime):
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_tools()
        self._init_session_manager()
        self._init_hooks()

        super().__init__(
            runtime=self.runtime,
            name="AnalystCoordinator",
            agent_id="analyst_coordinator",
            description="Coordinates the analysis of market, news, and fundamentals data to provide insights and recommendations.",
            system_prompt=self.system_prompt,
            tools=self.tools,
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
        settings = self.runtime.config.model_for("ANALYSTS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_tools(self):
        market_analyst = MarketAnalyst(runtime=self.runtime)
        news_analyst = NewsAnalyst(runtime=self.runtime)
        fundamentals_analyst = FundamentalsAnalyst(runtime=self.runtime)

        self.tools = [
            market_analyst.get_market_analyst_insights,
            news_analyst.get_news_analyst_insights,
            fundamentals_analyst.get_fundamentals_analyst_insights,
        ]

    def _init_session_manager(self):
        self.session_manager = self.runtime.session_for("analyst_coordinator")

    def _init_hooks(self):
        self.lifecycle_hooks = SharedDocument(runtime=self.runtime, memory=None)
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def get_analyst_coordinator_insights(self, message: str) -> AgentResult:
        """Get insights and recommendations from market, news, and fundamentals analysts for a specific ticker and date"""
        return await self.invoke_async(message)


if __name__ == "__main__":
    from runtime.examples import run_example

    run_example(AnalystCoordinator, "analyst_coordinator_report")
