import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.researchers.bull.hook import SharedDocument, StoreMemoryHook
from agents.researchers.bull.memory import MemoryService


class BullResearcher(Agent):
    def __init__(
        self,
        model_id="qwen3:8b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    ):
        self._init_system_prompt()
        self._init_model(model_id, base_url, api_key)
        self._init_session_manager("data/agents_sessions/researchers/bull_researcher")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="BullResearcherAgent",
            agent_id="bull_researcher",
            description="Analyses bull market trends and provides insights.",
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
        memory = MemoryService(agent_id="bull_researcher")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)
        store_memory_hook = StoreMemoryHook(memory)
        self.hooks = [shared_document_handler_hook, store_memory_hook]

    @tool
    async def get_bull_researcher_insights(self, message: str) -> AgentResult:
        """Get insights from the bull market researcher. Make a query for bull analyst."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio

    agent = BullResearcher()
    test_message = "Provide the bull market analysis."
    response = asyncio.run(agent.get_bull_researcher_insights(test_message))
    print(f"Response: {response}")
