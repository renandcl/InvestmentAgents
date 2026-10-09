import os

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.analysts.news_analyst.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime
from runtime.mcp import start_mcp


class NewsAnalyst(Agent):
    def __init__(self, *, runtime):
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_mcps()
        self._init_tools()
        self._init_session_manager()
        self._init_hooks()

        super().__init__(
            runtime=self.runtime,
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
        with open(
            os.path.join(os.path.dirname(__file__), "prompt.txt"), "r", encoding="utf-8"
        ) as f:
            self.system_prompt = f.read()

    def _init_model(self):
        settings = self.runtime.config.model_for("ANALYSTS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_mcps(self):
        self.stdio_mcp_finnhub_news_client = start_mcp(
            self.runtime, "finnhub-news-data-server", env_file=True
        )
        self.stdio_mcp_reddit_news_client = start_mcp(
            self.runtime, "reddit-news-data-server", env_file=True
        )
        self.stdio_mcp_duckduckgo_news_client = start_mcp(
            self.runtime, "duckduckgo-news-data-server", env_file=False
        )

    def _init_session_manager(self):
        self.session_manager = self.runtime.session_for("news_analyst")

    def _init_tools(self):
        self.tools = (
            self.stdio_mcp_finnhub_news_client.list_tools_sync()
            + self.stdio_mcp_reddit_news_client.list_tools_sync()
            + self.stdio_mcp_duckduckgo_news_client.list_tools_sync()
        )

    def _init_hooks(self):
        self.lifecycle_hooks = SharedDocument(runtime=self.runtime, memory=None)
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def get_news_analyst_insights(self, message: str) -> AgentResult:
        """Get news and trends analyst insights for investment decisions by requesting the analysis for ticker and date."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    from runtime.examples import run_example

    run_example(NewsAnalyst, "news_analyst_report")
