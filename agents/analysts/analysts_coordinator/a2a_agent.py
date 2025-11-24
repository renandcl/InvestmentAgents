import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

from agents.analysts.analysts_coordinator.hook import SharedDocument

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class AnalystCoordinator(Agent):
    """Coordinator agent that calls other analyst agents via A2A HTTP interfaces."""

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
            agent_id="coordinator",
            description="Coordinates market, news, and fundamentals analyses to produce recommendations.",
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
        # # Individual A2A client tool providers (remote analysts)
        fundamentals_analyst_url = "http://localhost:9900"
        news_analyst_url = "http://localhost:9901"
        market_analyst_url = "http://localhost:9902"
        provider = A2AClientToolProvider(
            known_agent_urls=[
                fundamentals_analyst_url,
                news_analyst_url,
                market_analyst_url,
            ]
        )
        self.tools = provider.tools

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
