import logging
import asyncio
import datetime
import os
from mcp import stdio_client, StdioServerParameters

from strands import Agent
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.tools.mcp import MCPClient

# Enables Strands debug log level
logging.getLogger("strands").setLevel(logging.INFO)

# Sets the logging format and streams logs to stderr
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class FundamentalsAnalystAgent:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.stdio_mcp_simfin_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=["run", "mcp-servers/simfin-fundamentals-data-server/main.py"],
                )
            )
        )

        self.stdio_mcp_finnhub_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=[
                        "run",
                        "--env-file",
                        "mcp-servers/finnhub-fundamentals-data-server/.env",
                        "mcp-servers/finnhub-fundamentals-data-server/main.py",
                    ],
                )
            )
        )
        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        # get system prompt
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()
            self.system_prompt = self.system_prompt.format(
                current_date=datetime.datetime.now().strftime("%Y-%m-%d")
            )

    async def invoke(self, message: str) -> AgentResult:
        # Create a Strands agent
        with self.stdio_mcp_simfin_client, self.stdio_mcp_finnhub_client:
            tools = self.stdio_mcp_simfin_client.list_tools_sync() + self.stdio_mcp_finnhub_client.list_tools_sync()
            logging.info(f"Available tools: {tools}")

            agent = Agent(
                name="FundamentalsAnalystAgent",
                description="hi",
                system_prompt=self.system_prompt,
                tools=tools,
                model=self.ollama_model,
            )
            return await agent.invoke_async(message)


if __name__ == "__main__":
    agent = FundamentalsAnalystAgent()
    test_message = "Get info for AAPL?"
    response = asyncio.run(agent.invoke(test_message))
    print(f"Response: {response}")
    logging.info(f"Response: {response}")