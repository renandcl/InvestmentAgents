import os
import uuid
from datetime import datetime

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel
from strands.session.file_session_manager import FileSessionManager
from strands.tools.mcp import MCPClient

from agents.analysts.news_analyst.hook import SharedDocument


class NewsAnalyst(Agent):
    def __init__(
        self,
    ):
        self._init_system_prompt()
        self._init_model()
        self._init_mcps()
        self._init_tools()
        self._init_session_manager("data/agents_sessions/analysts/news_analyst")
        self._init_hooks(shared_document_file="data/shared_document.json")

        super().__init__(
            name="NewsAnalystAgent",
            agent_id="news_analyst",
            description="Analyzes recent news and trends for trading and macroeconomics by requesting the analysis for ticker and date.",
            system_prompt=self.system_prompt,
            tools=self.tools,
            model=self.model,
            session_manager=self.session_manager,
            hooks=self.hooks,
        )

    def _init_system_prompt(self):
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

    def _init_model(self):
        base_url = os.getenv("ANALYSTS_BASE_URL", "http://localhost:11434/v1")
        api_key = os.getenv("ANALYSTS_API_KEY", "ollama")
        model_id = os.getenv("ANALYSTS_MODEL_ID", "qwen3:8b")
        self.model = OpenAIModel(
            client_args={
                "base_url": base_url,
                "api_key": api_key,
            },
            model_id=model_id,
        )

    def _init_mcps(self):
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

        self.stdio_mcp_finnhub_news_client.start()
        self.stdio_mcp_reddit_news_client.start()
        self.stdio_mcp_duckduckgo_news_client.start()

    def _init_session_manager(self, storage_dir: str):
        current_date = datetime.now().strftime("%Y%m%d%H%M%S")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}{uuid.uuid4().hex[:8]}",
            storage_dir=storage_dir,
        )

    def _init_tools(self):
        self.tools = (
            self.stdio_mcp_finnhub_news_client.list_tools_sync()
            + self.stdio_mcp_reddit_news_client.list_tools_sync()
            + self.stdio_mcp_duckduckgo_news_client.list_tools_sync()
        )

    def _init_hooks(self, shared_document_file: str):
        shared_document_handler_hook = SharedDocument(shared_document_file)
        self.hooks = [shared_document_handler_hook]

    @tool
    async def get_news_analyst_insights(self, message: str) -> AgentResult:
        """Get news and trends analyst insights for investment decisions by requesting the analysis for ticker and date."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    import asyncio
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
