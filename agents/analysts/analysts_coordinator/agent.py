import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.analysts.analysts_coordinator.hook import SharedDocument
from agents.analysts.fundamentals_analyst.agent import FundamentalsAnalyst
from agents.analysts.market_analyst.agent import MarketAnalyst
from agents.analysts.news_analyst.agent import NewsAnalyst

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class AnalystCoordinator(Agent):
    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_tools()
        self._init_session_manager("data/agents_sessions/analysts/analysts_coordinator")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
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
        market_analyst = MarketAnalyst()
        news_analyst = NewsAnalyst()
        fundamentals_analyst = FundamentalsAnalyst()

        self.tools = [
            market_analyst.get_market_analyst_insights,
            news_analyst.get_news_analyst_insights,
            fundamentals_analyst.get_fundamentals_analyst_insights,
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
    async def get_analyst_coordinator_insights(self, message: str) -> AgentResult:
        """Get insights and recommendations from market, news, and fundamentals analysts for a specific ticker and date"""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio
    import json

    ticker = "AAPL"
    date = "2025-08-01"
    with open("data/shared_document.json", "w") as f:
        json.dump({"ticker": ticker, "current_date": date}, f)

    test_message = "Provide the analysis"

    agent = AnalystCoordinator()
    response = asyncio.run(agent.get_analyst_coordinator_insights(test_message))
    print(f"Response: {response}")
