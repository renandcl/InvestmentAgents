import asyncio
import datetime
import logging
import os

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.tools.mcp import MCPClient

logging.getLogger("strands").setLevel(logging.INFO)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)

class MarketAnalystAgent:
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

        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()
            self.system_prompt = self.system_prompt.format(
                current_date=datetime.datetime.now().strftime("%Y-%m-%d")
            )

    async def invoke(self, message: str) -> AgentResult:
        # Open both MCP tool clients simultaneously
        with self.stdio_mcp_yfin_client, self.stdio_mcp_stockstats_client:
            tools = (
                self.stdio_mcp_yfin_client.list_tools_sync()
                + self.stdio_mcp_stockstats_client.list_tools_sync()
            )
            logging.info(f"Available tools: {tools}")

            agent = Agent(
                name="MarketAnalystAgent",
                description="Analyzes market data and technical indicators to produce nuanced trading insights.",
                system_prompt=self.system_prompt,
                tools=tools,
                model=self.ollama_model,
            )
            return await agent.invoke_async(message)

if __name__ == "__main__":
    agent = MarketAnalystAgent()
    test_message = "Analyze market indicators for AAPL"
    response = asyncio.run(agent.invoke(test_message))
    print(f"Response: {response}")
    logging.info(f"Response: {response}")
