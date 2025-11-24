import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.analysts.analysts_coordinator.agent import AnalystCoordinator
from agents.investment_manager.hook import SharedDocument
from agents.researchers.manager.agent import ResearchManager
from agents.risk_mgt.risk_manager.agent import RiskManager
from agents.traders.trader.agent import Trader

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

    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_tools()
        self._init_session_manager("data/agents_sessions/investment_manager")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
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
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self, model_id, base_url, api_key):
        self.model = OpenAIModel(
            client_args={
                "base_url": base_url,
                "api_key": api_key,
            },
            model_id=model_id,
        )

    def _init_tools(self):
        analyst_coordinator = AnalystCoordinator()
        research_manager = ResearchManager()
        trader = Trader()
        risk_manager = RiskManager()
        self.tools = [
            analyst_coordinator.get_analyst_coordinator_insights,
            research_manager.get_research_manager_investment_plan,
            trader.get_trader_investment_plan_decision,
            risk_manager.get_risk_manager_evaluation_and_decision,
        ]

    def _init_session_manager(self, storage_dir: str):
        current_date = datetime.now().strftime("%Y%m%d%H%M%S")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}{uuid.uuid4().hex[:8]}",
            storage_dir=storage_dir,
        )

    def _init_hooks(self, shared_document_file: str):
        shared_document_handler_hook = SharedDocument(shared_document_file)
        self.hooks = [shared_document_handler_hook]

    @tool
    async def execute_complete_workflow(self, message: str) -> AgentResult:
        """Execute the complete investment decision workflow."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio
    import json

    ticker = "AAPL"
    date = "2025-08-01"
    with open("data/shared_document.json", "w") as f:
        json.dump({"ticker": ticker, "current_date": date}, f)

    test_prompt = "Execute the investment analyses."

    investment_manager = InvestmentManager()
    response = asyncio.run(investment_manager.execute_complete_workflow(test_prompt))
    print(f"Response: {response}")
