import logging
import os

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.analysts.analysts_coordinator.agent import AnalystCoordinator
from agents.investment_manager.hook import SharedDocument
from agents.researchers.manager.agent import ResearchManager
from agents.risk_mgt.risk_manager.agent import RiskManager
from agents.traders.trader.agent import Trader
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class InvestmentManager(Agent):
    """
    Investment Manager - Main System Orchestrator

    Coordinates the complete investment decision workflow:
    1. Analysis Phase: Analysts Coordinator gathers market intelligence
    2. Research Phase: Research Manager evaluates bull/bear perspectives
    3. Trading Phase: Trader develops execution plan
    4. Risk Phase: Risk Manager evaluates and makes final decision
    5. Execution: Investment Manager approves/rejects execution
    """

    def __init__(self, *, runtime):
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_tools()
        self._init_session_manager()
        self._init_hooks()

        super().__init__(
            runtime=self.runtime,
            name="InvestmentManagerAgent",
            agent_id="investment_manager",
            description="Main orchestrator that coordinates the complete investment decision workflow across all agents",
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
        settings = self.runtime.config.model_for("INVESTMENT_MANAGER")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_tools(self):
        analyst_coordinator = AnalystCoordinator(runtime=self.runtime)
        research_manager = ResearchManager(runtime=self.runtime)
        trader = Trader(runtime=self.runtime)
        risk_manager = RiskManager(runtime=self.runtime)
        self.tools = [
            analyst_coordinator.get_analyst_coordinator_insights,
            research_manager.get_research_manager_investment_plan,
            trader.get_trader_investment_plan_decision,
            risk_manager.get_risk_manager_evaluation_and_decision,
        ]

    def _init_session_manager(self):
        self.session_manager = self.runtime.session_for("investment_manager")

    def _init_hooks(self):
        self.lifecycle_hooks = SharedDocument(runtime=self.runtime, memory=None)
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def execute_complete_workflow(self, message: str) -> AgentResult:
        """Execute the complete investment decision workflow."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    from runtime.examples import run_example

    run_example(InvestmentManager, "investment_manager_report")
