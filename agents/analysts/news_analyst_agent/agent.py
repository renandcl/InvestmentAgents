import asyncio
import datetime
import os
import logging

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.tools.mcp import MCPClient


class NewsAnalystAgent:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.stdio_mcp_finnhub_news_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=[
                        "run",
                        "--env-file",
                        "mcp-servers/finnhub-news-data-server/.env",
                        "mcp-servers/finnhub-news-data-server/main.py",
                    ],
                )
            )
        )
        self.stdio_mcp_reddit_news_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=[
                        "run",
                        "--env-file",
                        "mcp-servers/reddit-news-data-server/.env",
                        "mcp-servers/reddit-news-data-server/main.py",
                    ],
                )
            )
        )
        self.stdio_mcp_duckduckgo_news_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uv",
                    args=[
                        "run",
                        "mcp-servers/duckduckgo-news-data-server/main.py",
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

        self.stdio_mcp_finnhub_news_client.start()
        self.stdio_mcp_reddit_news_client.start()
        self.stdio_mcp_duckduckgo_news_client.start()

        tools = (
            self.stdio_mcp_finnhub_news_client.list_tools_sync()
            + self.stdio_mcp_reddit_news_client.list_tools_sync()
            + self.stdio_mcp_duckduckgo_news_client.list_tools_sync()
        )

        self.agent = Agent(
            name="NewsAnalystAgent",
            description="Analyzes recent news and trends for trading and macroeconomics.",
            system_prompt=self.system_prompt,
            tools=tools,
            model=self.ollama_model,
        )

    async def invoke(self, message: str) -> AgentResult:
        return await self.agent.invoke_async(message)

if __name__ == "__main__":
    agent = NewsAnalystAgent()
    test_message = "Get news for AAPL?"
    response = asyncio.run(agent.invoke(test_message))
    print(f"Response: {response}")
    logging.info(f"Response: {response}")
