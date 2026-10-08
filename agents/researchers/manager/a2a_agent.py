import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.hooks.contracts import ContractError
from agents.researchers.manager.hook import SharedDocument
from agents.researchers.manager.memory import MemoryService

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class ResearchManager(Agent):
    """Distributed variant reserved until HTTP round-context propagation is supported."""

    def __init__(self):
        raise ContractError(
            "Distributed research debates require HTTP round-context propagation; "
            "use the in-process manager from agent.py."
        )

    def _init_system_prompt(self):
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self):
        base_url = os.getenv("RESEARCHERS_BASE_URL") or "http://localhost:11434/v1"
        api_key = os.getenv("RESEARCHERS_API_KEY") or "ollama"
        model_id = os.getenv("RESEARCHERS_MODEL_ID") or "qwen3:8b"
        self.model = OpenAIModel(
            client_args={
                "base_url": base_url,
                "api_key": api_key,
            },
            model_id=model_id,
        )

    def _init_session_manager(self, storage_dir: str):
        current_date = datetime.now().strftime("%Y%m%d%H%M%S")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}{uuid.uuid4().hex[:8]}",
            storage_dir=storage_dir,
        )

    def _init_hooks(self, shared_document_file: str):
        memory = MemoryService(agent_id="research_manager")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)
        self.hooks = [shared_document_handler_hook]

    def _init_tools(self):
        self.tools = []

    @tool
    async def get_research_manager_investment_plan(self, message: str) -> AgentResult:
        """Get researcher manager to critically evaluate the research from both bull and bear analysts and make an informed investment plan."""
        return await self.invoke_async(message)
