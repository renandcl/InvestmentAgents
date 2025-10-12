import asyncio
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from agents.traders.trader.hook import SharedStateHandler
from agents.traders.trader.memory import MemoryService


class Trader:
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
            storage_dir="data/agents_sessions/traders/trader",
        )

        shared_state_file = "data/shared_state.json"
        memory = MemoryService(agent_id="trader")
        shared_state_handler_hook = SharedStateHandler(shared_state_file, memory)

        self.agent = Agent(
            name="TraderAgent",
            agent_id="trader",
            description="Executes investment decisions based on the research manager's plan.",
            system_prompt=self.system_prompt,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_state_handler_hook],
        )

    @tool
    async def execute_investment_decision(self, message: str) -> AgentResult:
        """Execute the investment decision based on the research manager's plan."""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    # state = {
    #     "ticker": "AAPL",
    #     "current_date": "2025-10-12",
    #     "investment_plan": "BUY recommendation based on strong fundamentals...",
    # }
    # with open("data/shared_state.json", "w") as f:
    #     json.dump(state, f)
    with open("data/shared_state.json", "r") as f:
        state = json.load(f)
    agent = Trader()
    test_message = "Execute the investment decision based on the plan."
    response = asyncio.run(agent.execute_investment_decision(test_message))
    print(f"Response: {response}")
