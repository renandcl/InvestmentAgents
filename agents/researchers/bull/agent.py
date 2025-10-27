import asyncio
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from agents.researchers.bull.hook import SharedDocument
from agents.researchers.bull.memory import MemoryService


class BullResearcher:
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
            storage_dir="data/agents_sessions/researchers/bull_researcher",
        )

        shared_document_file = "data/shared_document.json"
        memory = MemoryService(agent_id="bull_researcher")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)

        self.agent = Agent(
            name="BullResearcherAgent",
            agent_id="bull_researcher",
            description="Analyses bull market trends and provides insights.",
            system_prompt=self.system_prompt,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_document_handler_hook],
        )

    @tool
    async def get_bull_researcher_insights(self, message: str) -> AgentResult:
        """Get insights from the bull market researcher."""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    # state = {
    #     "ticker": "AAPL",
    #     "current_date": "2025-08-01",
    # }
    # with open("data/shared_document.json", "w") as f:
    #     json.dump(state, f)
    with open("data/shared_document.json", "r") as f:
        state = json.load(f)
    agent = BullResearcher()
    test_message = "Provide the bull market analysis."
    response = asyncio.run(agent.get_bull_researcher_insights(test_message))
    print(f"Response: {response}")
