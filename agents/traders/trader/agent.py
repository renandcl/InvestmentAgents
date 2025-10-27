import asyncio
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from agents.traders.trader.hook import SharedDocument
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

        shared_document_file = "data/shared_document.json"
        memory = MemoryService(agent_id="trader")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)

        self.agent = Agent(
            name="TraderAgent",
            agent_id="trader",
            description="Analyzes market data to make informed and strategic investment plans.",
            system_prompt=self.system_prompt,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_document_handler_hook],
        )

    @tool
    async def get_trader_investment_plan_decision(self, message: str) -> AgentResult:
        """Get the trading agent to analyze market data to make an informed and strategic investment plandecision"""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    # state = {
    #     "ticker": "AAPL",
    #     "current_date": "2025-10-12",
    #     "investment_plan": "BUY recommendation based on strong fundamentals...",
    # }
    # with open("data/shared_document.json", "w") as f:
    #     json.dump(state, f)
    with open("data/shared_document.json", "r") as f:
        state = json.load(f)
    agent = Trader()
    test_message = "Execute the investment decision based on the plan."
    response = asyncio.run(agent.get_trader_investment_plan_decision(test_message))
    print(f"Response: {response}")
