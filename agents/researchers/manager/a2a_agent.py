import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

from agents.researchers.manager.hook import SharedDocument
from agents.researchers.manager.memory import MemoryService

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class ResearchManager:
    """Research Manager agent that coordinates bull and bear researchers via A2A HTTP interfaces."""

    def __init__(
        self, model_id: str = "qwen3:8b", host: str = "http://localhost:11434"
    ):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(host=self.host, model_id=self.model_id)

        # A2A client tool providers for remote researchers
        bull_researcher_url = "http://localhost:9905"
        bear_researcher_url = "http://localhost:9904"
        provider = A2AClientToolProvider(
            known_agent_urls=[
                bull_researcher_url,
                bear_researcher_url,
            ]
        )

        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/researchers/research_manager",
        )

        tools = provider.tools
        shared_document_file = "data/shared_document.json"
        memory = MemoryService(agent_id="research_manager")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)

        self.agent = Agent(
            name="ResearchManagerAgent",
            agent_id="research_manager",
            description="Critically evaluates research from both bull and bear analysts and makes an informed investment plan.",
            system_prompt=self.system_prompt,
            tools=tools,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_document_handler_hook],
        )

    @tool
    async def get_research_manager_investment_plan(self, message: str) -> AgentResult:
        """Get researcher manager to critically evaluate the research from both bull and bear analysts and make an informed investment plan."""
        return await self.agent.invoke_async(message)
