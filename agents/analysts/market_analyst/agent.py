import asyncio
import os
import uuid
from datetime import datetime

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient


class MarketAnalyst:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        # MCP client for Yahoo Finance market data
        self.stdio_mcp_yfin_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=[
                        "run",
                        "mcp-servers/yfin-market-data-server/main.py",
                    ],
                )
            )
        )
        # MCP client for stockstats indicators
        self.stdio_mcp_stockstats_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=[
                        "run",
                        "mcp-servers/stockstats-market-data-server/main.py",
                    ],
                )
            )
        )

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        current_date = datetime.now().strftime("%Y-%m-%d")
        # get system prompt
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/market_analyst",
        )

        self.stdio_mcp_yfin_client.start()
        self.stdio_mcp_stockstats_client.start()

        tools = (
            self.stdio_mcp_yfin_client.list_tools_sync()
            + self.stdio_mcp_stockstats_client.list_tools_sync()
        )

        self.agent = Agent(
            name="MarketAnalystAgent",
            description="Analyzes market data and technical indicators to produce nuanced trading insights by providing ticker and date.",
            system_prompt=self.system_prompt,
            tools=tools,
            model=self.ollama_model,
            session_manager=self.session_manager,
        )

    @tool
    async def get_market_analyst_insights(self, message: str) -> AgentResult:
        """Get market data and technical indicators analyst insights for investment decisions by providing ticker and date."""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    ticker = "AAPL"
    date = "2025-08-01"
    test_message = f"The company we want to look at is {ticker}. For your reference, the current date is {date}."
    agent = MarketAnalyst()
    response = asyncio.run(agent.get_market_analyst_insights(test_message))
    print(f"Response: {response}")
