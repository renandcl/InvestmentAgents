import asyncio
import uuid
from datetime import datetime
import logging

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands_tools.a2a_client import A2AClientToolProvider
from strands.session.file_session_manager import FileSessionManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalystCoordinatorAgent:
    """Coordinator agent that calls other analyst agents via A2A HTTP interfaces."""

    def __init__(self, model_id: str = "qwen3:8b", host: str = "http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(host=self.host, model_id=self.model_id)

        # Individual A2A client tool providers (remote analysts)
        fundamentals_provider = A2AClientToolProvider(known_agent_urls=["http://127.0.0.1:9900"])
        news_provider = A2AClientToolProvider(known_agent_urls=["http://127.0.0.1:9901"])
        market_provider = A2AClientToolProvider(known_agent_urls=["http://127.0.0.1:9902"])

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/analysts_coordinator",
        )
        # Flatten tool lists
        tools = (
            fundamentals_provider.tools
            + news_provider.tools
            + market_provider.tools
        )
        self.agent = Agent(
            name="AnalystCoordinator",
            description="Coordinates market, news, and fundamentals analyses to produce recommendations.",
            system_prompt=(
                "You coordinate specialized analyst agents (market, news, fundamentals). "
                "Use their tools to gather insights, synthesize them, and produce a clear BUY/HOLD/SELL recommendation with concise rationale."
            ),
            tools=tools,
            model=self.ollama_model,
        )

    @tool
    async def get_analysts_insights(self, message: str) -> AgentResult:
        """Query all underlying analyst agents and aggregate their insights for a ticker/date."""
        return await self.agent.invoke_async(message)


async def _demo():
    coordinator = AnalystCoordinatorAgent()
    test_message = (
        "Analyse AAPL for date 2025-08-01. Provide final BUY/HOLD/SELL recommendation."  # noqa: E501
    )
    result = await coordinator.get_analysts_insights(test_message)
    print(result)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_demo())
