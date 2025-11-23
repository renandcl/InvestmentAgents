import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

from agents.researchers.manager.hook import SharedDocument
from agents.researchers.manager.memory import MemoryService

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class ResearchManager(Agent):
    """Research Manager agent that coordinates bull and bear researchers via A2A HTTP interfaces."""

    def __init__(
        self,
        model_id: str = "qwen3:8b",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_session_manager("data/agents_sessions/researchers/research_manager")
        self._init_hooks(shared_document_file="data/shared_document.json")
        self._init_tools()

        super().__init__(
            name="ResearchManagerAgent",
            agent_id="research_manager",
            description="Critically evaluates research from both bull and bear analysts and makes an informed investment plan.",
            system_prompt=self.system_prompt,
            tools=self.tools,
            model=self.openai_model,
            session_manager=self.session_manager,
            hooks=[self.shared_document_handler_hook],
        )

    def _init_system_prompt(self):
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self, model_id, base_url, api_key):
        self.openai_model = OpenAIModel(
            client_args={
                "base_url": base_url,
                "api_key": api_key,
            },
            model_id=model_id,
        )

    def _init_session_manager(self, storage_dir: str):
        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir=storage_dir,
        )

    def _init_hooks(self, shared_document_file: str):
        memory = MemoryService(agent_id="research_manager")
        self.shared_document_handler_hook = SharedDocument(shared_document_file, memory)

    def _init_tools(self):
        # A2A client tool providers for remote researchers
        bear_researcher_url = "http://localhost:9904"
        bull_researcher_url = "http://localhost:9905"
        provider = A2AClientToolProvider(
            known_agent_urls=[
                bear_researcher_url,
                bull_researcher_url,
            ]
        )
        self.tools = provider.tools

    @tool
    async def get_research_manager_investment_plan(self, message: str) -> AgentResult:
        """Get researcher manager to critically evaluate the research from both bull and bear analysts and make an informed investment plan."""
        return await self.invoke_async(message)
