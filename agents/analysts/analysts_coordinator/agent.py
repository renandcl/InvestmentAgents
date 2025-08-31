import asyncio
import logging
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from agents.analysts.fundamentals_analyst_agent.agent import FundamentalsAnalystAgent
from agents.analysts.market_analyst_agent.agent import MarketAnalystAgent
from agents.analysts.news_analyst_agent.agent import NewsAnalystAgent

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class AnalystCoordinatorAgent:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        market_analyst = MarketAnalystAgent()
        news_analyst = NewsAnalystAgent()
        fundamentals_analyst = FundamentalsAnalystAgent()

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/analysts_coordinator",
        )
        self.agent = Agent(
            name="AnalystCoordinator",
            description="Coordinates the analysis of market, news, and fundamentals data to provide insights and recommendations.",
            system_prompt="You are an expert analyst coordinating the analysis of market, news, and fundamentals data to provide insights and recommendations.",
            tools=[
                market_analyst.get_market_analyst_insights,
                news_analyst.get_news_analyst_insights,
                fundamentals_analyst.get_fundamentals_analyst_insights,
            ],
            model=self.ollama_model,
        )

    @tool
    async def get_analysts_insights(self, message: str) -> AgentResult:
        """Get insights and recommendations from market, news, and fundamentals analysts for a specific ticker and date"""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    test_message = """
    Analyse AAPL for date 2025-08-01

    Discuss between the agents to come to a consensus on the best course of action.

    Finally, provide a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** with a concise rationale in 1-2 sentences.
    """
    agent = AnalystCoordinatorAgent()
    response = asyncio.run(agent.get_analysts_insights(test_message))
    print(f"Response: {response}")
