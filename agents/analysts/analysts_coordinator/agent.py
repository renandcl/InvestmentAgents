import asyncio
import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from agents.analysts.analysts_coordinator.hook import SharedStateHandler
from agents.analysts.fundamentals_analyst.agent import FundamentalsAnalyst
from agents.analysts.market_analyst.agent import MarketAnalyst
from agents.analysts.news_analyst.agent import NewsAnalyst

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class AnalystCoordinator:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        market_analyst = MarketAnalyst()
        news_analyst = NewsAnalyst()
        fundamentals_analyst = FundamentalsAnalyst()

        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/analysts_coordinator",
        )

        shared_state_file = "data/shared_state.json"
        shared_state_handler_hook = SharedStateHandler(shared_state_file)

        self.agent = Agent(
            name="AnalystCoordinator",
            agent_id="coordinator",
            description="Coordinates the analysis of market, news, and fundamentals data to provide insights and recommendations.",
            system_prompt=self.system_prompt,
            tools=[
                market_analyst.get_market_analyst_insights,
                news_analyst.get_news_analyst_insights,
                fundamentals_analyst.get_fundamentals_analyst_insights,
            ],
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_state_handler_hook],
        )

    @tool
    async def get_analysts_insights(self, message: str) -> AgentResult:
        """Get insights and recommendations from market, news, and fundamentals analysts for a specific ticker and date"""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    ticker = "AAPL"
    date = "2025-08-01"
    with open("data/shared_state.json", "w") as f:
        json.dump({"ticker": ticker, "current_date": date}, f)

    test_message = "Provide the analysis"

    agent = AnalystCoordinator()
    response = asyncio.run(agent.get_analysts_insights(test_message))
    print(f"Response: {response}")
