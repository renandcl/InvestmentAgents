import asyncio
import os
import uuid
from datetime import datetime

from hook import SharedStateHandler
from memory import MemoryService
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager


class BearResearcher:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host
        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        # get system prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/researchers/bear_researcher",
        )

        shared_state_file = "data/shared_state.json"
        memory = MemoryService(agent_id="bear_researcher")
        shared_state_handler_hook = SharedStateHandler(shared_state_file, memory)

        self.agent = Agent(
            name="BearResearcherAgent",
            agent_id="bear_researcher",
            description="Analyses bear market trends and provides insights.",
            system_prompt=self.system_prompt,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_state_handler_hook],
        )

    @tool
    async def get_bear_researcher_insights(self, message: str) -> AgentResult:
        """Get insights from the bear market researcher."""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    # state = {
    #     "ticker": "AAPL",
    #     "current_date": "2025-08-01",
    # }
    # with open("data/shared_state.json", "w") as f:
    #     json.dump(state, f)
    with open("data/shared_state.json", "r") as f:
        state = json.load(f)
    agent = BearResearcher()
    test_message = "Provide the bear market analysis."
    response = asyncio.run(agent.get_bear_researcher_insights(test_message))
    print(f"Response: {response}")
