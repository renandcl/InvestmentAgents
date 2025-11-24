import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.risk_mgt.aggressive_debator.agent import AggressiveDebator
from agents.risk_mgt.conservative_debator.agent import ConservativeDebator
from agents.risk_mgt.neutral_debator.agent import NeutralDebator
from agents.risk_mgt.risk_manager.hook import SharedDocument, StoreMemoryHook
from agents.risk_mgt.risk_manager.memory import MemoryService

# Enable debug logs
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class RiskManager(Agent):
    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_session_manager("data/agents_sessions/risk_mgt/risk_manager")
        self._init_hooks(shared_document_file="data/shared_document.json")
        self._init_tools()

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

    def _init_tools(self):
        aggressive_debator = AggressiveDebator()
        conservative_debator = ConservativeDebator()
        neutral_debator = NeutralDebator()
        self.tools = [
            aggressive_debator.get_aggressive_analysis,
            conservative_debator.get_conservative_analysis,
            neutral_debator.get_neutral_analysis,
        ]

    @tool
    async def get_risk_manager_evaluation_and_decision(self, query: str) -> AgentResult:
        """
        Evaluates risk perspectives. Coordinates three risk analysts to debate, then synthesizes their arguments into a final risk-adjusted recommendation.
        """
        return await self.invoke_async(query)


if __name__ == "__main__":
    import asyncio

    risk_manager = RiskManager()
    result = asyncio.run(
        risk_manager.get_risk_manager_evaluation_and_decision(
            "Coordinate a debate between the aggressive, conservative, and neutral analysts to make a final risk-adjusted trading decision."
        )
    )
    print(result)
