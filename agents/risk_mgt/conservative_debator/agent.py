import asyncio
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.risk_mgt.conservative_debator.hook import SharedDocument


class ConservativeDebator(Agent):
    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_session_manager("data/agents_sessions/risk_mgt/conservative_debator")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="ConservativeDebator",
            agent_id="conservative_risk_analyst",
            description="Conservative Risk Analyst that prioritizes asset protection, stability, and risk mitigation strategies",
            system_prompt=self.system_prompt,
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
        self.shared_document_handler_hook = SharedDocument(shared_document_file)

    @tool
    async def get_conservative_analysis(self, message: str) -> AgentResult:
        """Get conservative risk analysis for debate. Make a query for conservative analyst."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import json

    # state = {
    #     "ticker": "AAPL",
    #     "current_date": "2025-10-12",
    #     "trader_investment_plan": "BUY recommendation...",
    # }
    # with open("data/shared_document.json", "w") as f:
    #     json.dump(state, f)

    if os.path.exists("data/shared_document.json"):
        with open("data/shared_document.json", "r") as f:
            state = json.load(f)

    agent = ConservativeDebator()
    test_message = "Provide your conservative risk analysis of the trader's decision."
    response = asyncio.run(agent.provide_conservative_analysis(test_message))
    print(f"Response: {response}")
