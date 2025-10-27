import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

from hook import SharedDocument
from memory import MemoryService

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class RiskManager:
    """Risk Manager agent that coordinates aggressive, conservative, and neutral debators via A2A HTTP interfaces."""

    def __init__(
        self, model_id: str = "qwen3:8b", host: str = "http://localhost:11434"
    ):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(host=self.host, model_id=self.model_id)

        # A2A client tool providers for remote debators
        aggressive_debator_url = "http://localhost:9908"
        conservative_debator_url = "http://localhost:9909"
        neutral_debator_url = "http://localhost:9910"
        
        provider = A2AClientToolProvider(
            known_agent_urls=[
                aggressive_debator_url,
                conservative_debator_url,
                neutral_debator_url,
            ]
        )

        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/risk_mgt/risk_manager",
        )

        tools = provider.tools
        shared_document_file = "data/shared_document.json"
        memory = MemoryService(agent_id="risk_manager")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)

        self.agent = Agent(
            name="RiskManagerAgent",
            agent_id="risk_manager",
            description="Evaluates risk debate between aggressive, conservative, and neutral analysts to make final risk-adjusted trading decisions.",
            system_prompt=self.system_prompt,
            tools=tools,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[
                shared_document_handler_hook.get_shared_document,
                shared_document_handler_hook.add_prompt_reports,
                shared_document_handler_hook.save_shared_document,
            ],
        )

    @tool
    async def evaluate_risk_and_decide(self, message: str) -> AgentResult:
        """Evaluate risk from multiple perspectives and make final risk-adjusted trading decision."""
        return await self.agent.invoke_async(message)
