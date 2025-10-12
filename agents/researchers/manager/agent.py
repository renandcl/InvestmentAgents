import asyncio
import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from agents.researchers.manager.memory import MemoryService
from agents.researchers.manager.hook import SharedStateHandler
from agents.researchers.bull.agent import BullResearcher
from agents.researchers.bear.agent import BearResearcher

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class ResearchManager:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        bear_researcher = BearResearcher()
        bull_researcher = BullResearcher()

        # get system prompt
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        current_date = datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/researchers/research_manager",
        )

        shared_state_file = "data/shared_state.json"
        memory = MemoryService(agent_id="research_manager")
        shared_state_handler_hook = SharedStateHandler(shared_state_file, memory)

        self.agent = Agent(
            name="ResearchManagerAgent",
            agent_id="research_manager",
            description="Evaluates bull and bear research and makes final investment recommendations.",
            system_prompt=self.system_prompt,
            tools=[
                bear_researcher.get_bear_researcher_insights,
                bull_researcher.get_bull_researcher_insights,
            ],
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_state_handler_hook],
        )

    @tool
    async def get_research_manager_decision(self, message: str) -> AgentResult:
        """Get final investment decision from the research manager after evaluating bull and bear analyses."""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    # state = {
    #     "ticker": "AAPL",
    #     "current_date": "2025-08-01",
    #     "bull_researcher_report": "Strong buy signal...",
    #     "bear_researcher_report": "High risk concerns...",
    # }
    with open("data/shared_state.json", "r") as f:
        state = json.load(f)
    agent = ResearchManager()

    test_message = "Coordinate a debate between bull and bear researchers and provide your final investment recommendation."
    
    response = asyncio.run(agent.get_research_manager_decision(test_message))
    print(f"Response: {response}")
