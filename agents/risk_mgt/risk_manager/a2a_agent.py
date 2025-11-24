import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

from agents.risk_mgt.risk_manager.hook import SharedDocument, StoreMemoryHook
from agents.risk_mgt.risk_manager.memory import MemoryService

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class RiskManager(Agent):
    """Risk Manager agent that coordinates aggressive, conservative, and neutral debators via A2A HTTP interfaces."""

    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_tools()
        self._init_session_manager("data/agents_sessions/risk_mgt/risk_manager")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="RiskManagerAgent",
            agent_id="risk_manager",
            description="Evaluates risk debate between aggressive, conservative, and neutral analysts to make final risk-adjusted trading decisions.",
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
        self.tools = provider.tools

    def _init_session_manager(self, storage_dir: str):
        current_date = datetime.now().strftime("%Y%m%d%H%M%S")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}{uuid.uuid4().hex[:8]}",
            storage_dir=storage_dir,
        )

    def _init_hooks(self, shared_document_file: str):
        memory_service = MemoryService(agent_id="risk_manager")
        shared_document_handler_hook = SharedDocument(
            shared_document_file=shared_document_file, memory=memory_service
        )
        store_memory_hook = StoreMemoryHook(memory_service=memory_service)
        self.hooks = [shared_document_handler_hook, store_memory_hook]

    @tool
    async def evaluate_risk_and_decide(self, message: str) -> AgentResult:
        """Evaluate risk from multiple perspectives and make final risk-adjusted trading decision."""
        return await self.invoke_async(message)
