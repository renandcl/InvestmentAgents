import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.traders.trader.hook import SharedDocument, StoreMemoryHook
from agents.traders.trader.memory import MemoryService


class Trader(Agent):
    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_session_manager("data/agents_sessions/traders/trader")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="TraderAgent",
            agent_id="trader",
            description="Analyzes market data to make informed and strategic investment plans.",
            system_prompt=self.system_prompt,
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
        memory = MemoryService(agent_id="trader")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)
        store_memory_hook = StoreMemoryHook(memory_service=memory)
        self.hooks = [shared_document_handler_hook, store_memory_hook]

    @tool
    async def get_trader_investment_plan_decision(self, message: str) -> AgentResult:
        """Get the trading agent to analyze market data to make an informed and strategic investment plandecision"""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio

    agent = Trader()
    test_message = "Execute the investment decision based on the plan."
    response = asyncio.run(agent.get_trader_investment_plan_decision(test_message))
    print(f"Response: {response}")
