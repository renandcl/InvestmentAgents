from __future__ import annotations

import os
from typing import TYPE_CHECKING

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.analysts.social_media.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime
from runtime.examples import run_example
from runtime.mcp import start_mcp

if TYPE_CHECKING:
    from runtime.lifecycle import RunRuntime


class SocialMediaAnalyst(Agent):
    def __init__(self, *, runtime: RunRuntime) -> None:
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_mcps()
        self._init_tools()
        self._init_session_manager()
        self._init_hooks()

        super().__init__(
            runtime=self.runtime,
            name="SocialMediaAnalystAgent",
            agent_id="social_media_analyst",
            description="Analyzes Reddit opinions, attention and sentiment for a ticker and date; social claims are unverified.",
            system_prompt=self.system_prompt,
            tools=self.tools,
            model=self.model,
            session_manager=self.session_manager,
            hooks=self.hooks,
        )

    def _init_system_prompt(self) -> None:
        with open(
            os.path.join(os.path.dirname(__file__), "prompt.txt"), "r", encoding="utf-8"
        ) as f:
            self.system_prompt = f.read()

    def _init_model(self) -> None:
        settings = self.runtime.config.model_for("ANALYSTS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_mcps(self) -> None:
        self.stdio_mcp_reddit_news_client = start_mcp(
            self.runtime, "reddit-news-data-server", env_file=True
        )

    def _init_session_manager(self) -> None:
        self.session_manager = self.runtime.session_for("social_media_analyst")

    def _init_tools(self) -> None:
        self.tools = [
            tool
            for tool in self.stdio_mcp_reddit_news_client.list_tools_sync()
            if tool.tool_name == "get_reddit_sentiment"
        ]

    def _init_hooks(self) -> None:
        self.lifecycle_hooks = SharedDocument(runtime=self.runtime, memory=None)
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def get_social_media_analyst_insights(self, message: str) -> AgentResult:
        """Get Reddit sentiment and attention analysis for a ticker and date, separately from reported news."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    run_example(SocialMediaAnalyst, "social_media_analyst_report")
