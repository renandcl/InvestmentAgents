import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager

from agents.researchers.bear.agent import BearResearcher
from agents.researchers.bull.agent import BullResearcher
from agents.researchers.manager.hook import SharedDocument, StoreMemoryHook
from agents.researchers.manager.memory import MemoryService

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class ResearchManager(Agent):
    def __init__(
        self,
    ):
        self._init_system_prompt()
        self._init_model()
        self._init_session_manager("data/agents_sessions/researchers/research_manager")
        self._init_hooks(shared_document_file="data/shared_document.json")
        self._init_tools()

        super().__init__(
            name="ResearchManagerAgent",
            agent_id="research_manager",
            description="Critically evaluates research from both bull and bear analysts and makes an informed investment plan.",
            system_prompt=self.system_prompt,
            tools=self.tools,
            model=self.model,
            session_manager=self.session_manager,
            hooks=self.hooks,
        )

    def _init_system_prompt(self):
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self):
        base_url = os.getenv("RESEARCHERS_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("RESEARCHERS_API_KEY", "ollama")
        model_id = os.getenv("RESEARCHERS_MODEL_ID", "qwen3:8b")
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
        store_memory_hook = StoreMemoryHook(memory)
        self.hooks = [shared_document_handler_hook, store_memory_hook]

    def _init_tools(self):
        bear_researcher = BearResearcher()
        bull_researcher = BullResearcher()
        self.tools = [
            bear_researcher.get_bear_researcher_insights,
            bull_researcher.get_bull_researcher_insights,
        ]

    @tool
    async def get_research_manager_investment_plan(self, message: str) -> AgentResult:
        """Get researcher manager to critically evaluate the research from both bull and bear analysts and make an informed investment plan."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio

    agent = ResearchManager()
    test_message = "Coordinate a debate between bull and bear researchers and provide your final investment recommendation."
    response = asyncio.run(agent.get_research_manager_investment_plan(test_message))
    print(f"Response: {response}")
