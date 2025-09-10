import logging
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class AnalystCoordinator:
    """Coordinator agent that calls other analyst agents via A2A HTTP interfaces."""

    def __init__(
        self, model_id: str = "qwen3:8b", host: str = "http://localhost:11434"
    ):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(host=self.host, model_id=self.model_id)

        # # Individual A2A client tool providers (remote analysts)
        fundamentals_analyst_url = "http://localhost:9900"
        news_analyst_url = "http://localhost:9901"
        market_analyst_url = "http://localhost:9902"
        provider = A2AClientToolProvider(
            known_agent_urls=[fundamentals_analyst_url, news_analyst_url, market_analyst_url]
        )

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/analysts_coordinator",
        )
        tools = provider.tools
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
