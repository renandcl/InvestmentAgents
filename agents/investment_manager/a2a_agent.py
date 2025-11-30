import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands_tools.a2a_client import A2AClientToolProvider

from agents.investment_manager.hook import SharedDocument

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
)


class InvestmentManager(Agent):
    """
    Investment Manager - Main System Orchestrator

    Coordinates the complete investment decision workflow:
    1. Analysis Phase: Analysts Coordinator gathers market intelligence
    2. Research Phase: Research Manager evaluates bull/bear perspectives
    3. Trading Phase: Trader develops execution plan
    4. Risk Phase: Risk Manager evaluates and makes final decision
    5. Execution: Investment Manager approves/rejects execution
    """

    def __init__(
        self,
    ):
        self._init_system_prompt()
        self._init_model()
        self._init_tools()
        self._init_session_manager("data/agents_sessions/investment_manager")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="InvestmentManagerAgent",
            agent_id="investment_manager",
            description="Main orchestrator that coordinates the complete investment decision workflow across all agents",
            system_prompt=self.system_prompt,
            tools=self.tools,
            model=self.model,
            session_manager=self.session_manager,
            hooks=[self.shared_document_handler_hook],
        )

    def _init_system_prompt(self):
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self):
        base_url = os.getenv("INVESTMENT_MANAGER_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("INVESTMENT_MANAGER_API_KEY", "ollama")
        model_id = os.getenv("INVESTMENT_MANAGER_MODEL_ID", "qwen3:8b")
        self.model = OpenAIModel(
            client_args={
                "base_url": base_url,
                "api_key": api_key,
            },
            model_id=model_id,
        )

    def _init_tools(self):
        # A2A client tool providers for remote agents
        analyst_coordinator_url = "http://localhost:9903"
        research_manager_url = "http://localhost:9906"
        trader_url = "http://localhost:9907"
        risk_manager_url = "http://localhost:9911"

        provider = A2AClientToolProvider(
            known_agent_urls=[
                analyst_coordinator_url,
                research_manager_url,
                trader_url,
                risk_manager_url,
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
        self.shared_document_handler_hook = SharedDocument(
            shared_document_file=shared_document_file
        )

    @tool
    async def execute_complete_workflow(self, message: str) -> AgentResult:
        """Execute the complete investment decision workflow."""
        return await self.invoke_async(message)
