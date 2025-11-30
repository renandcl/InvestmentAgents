import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.risk_mgt.neutral_debator.hook import SharedDocument


class NeutralDebator(Agent):
    def __init__(
        self,
    ):
        self._init_system_prompt()
        self._init_model()
        self._init_session_manager("data/agents_sessions/risk_mgt/neutral_debator")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="NeutralDebator",
            agent_id="neutral_risk_analyst",
            description="Neutral Risk Analyst that prioritizes asset protection, stability, and risk mitigation strategies",
            system_prompt=self.system_prompt,
            model=self.model,
            session_manager=self.session_manager,
            hooks=self.hooks,
        )

    def _init_system_prompt(self):
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self):
        base_url = os.getenv("RISK_MANAGERS_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("RISK_MANAGERS_API_KEY", "ollama")
        model_id = os.getenv("RISK_MANAGERS_MODEL_ID", "qwen3:8b")
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
        shared_document_handler_hook = SharedDocument(shared_document_file)
        self.hooks = [shared_document_handler_hook]

    @tool
    async def get_neutral_analysis(self, message: str) -> AgentResult:
        """Get neutral risk analysis for debate. Make a query for neutral analyst."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio

    agent = NeutralDebator()
    test_message = "Provide your neutral risk analysis of the trader's decision."
    response = asyncio.run(agent.get_neutral_analysis(test_message))
    print(f"Response: {response}")
