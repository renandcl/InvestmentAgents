import asyncio
import os
import uuid
from datetime import datetime

from hook import SharedDocument
from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient


class NewsAnalyst:
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

        current_date = datetime.now().strftime("%Y-%m-%d")
        # get system prompt
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/analysts/news_analyst",
        )

        self.stdio_mcp_finnhub_news_client.start()
        self.stdio_mcp_reddit_news_client.start()
        self.stdio_mcp_duckduckgo_news_client.start()

        tools = (
            self.stdio_mcp_finnhub_news_client.list_tools_sync()
            + self.stdio_mcp_reddit_news_client.list_tools_sync()
            + self.stdio_mcp_duckduckgo_news_client.list_tools_sync()
        )

        shared_document_file = "data/shared_document.json"
        shared_document_handler_hook = SharedDocument(shared_document_file)

        self.agent = Agent(
            name="NewsAnalystAgent",
            agent_id="news",
            description="Analyzes recent news and trends for trading and macroeconomics by requesting the analysis for ticker and date.",
            system_prompt=self.system_prompt,
            tools=tools,
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[shared_document_handler_hook],
        )

    @tool
    async def get_news_analyst_insights(self, message: str) -> AgentResult:
        """Get news and trends analyst insights for investment decisions by requesting the analysis for ticker and date."""
        return await self.agent.invoke_async(message)


if __name__ == "__main__":
    import json

    state = {
        "ticker": "AAPL",
        "current_date": "2025-08-01",
    }
    with open("data/shared_document.json", "w") as f:
        json.dump(state, f)
    test_message = "Provide the analysis"
    agent = NewsAnalyst()
    response = asyncio.run(agent.get_news_analyst_insights(test_message))
    print(f"Response: {response}")
