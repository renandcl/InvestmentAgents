from __future__ import annotations

import os
from typing import TYPE_CHECKING

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.analysts.fundamentals_analyst.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime
from runtime.examples import run_example
from runtime.mcp import start_mcp

if TYPE_CHECKING:
    from runtime.lifecycle import RunRuntime


class FundamentalsAnalyst(Agent):
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
            name="FundamentalsAnalystAgent",
            agent_id="fundamentals_analyst",
            description="Analyzes fundamental data and provides insights for investment decisions by providing ticker and date.",
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
        self.stdio_mcp_simfin_client = start_mcp(
            self.runtime, "simfin-fundamentals-data-server", env_file=False
        )
        self.stdio_mcp_finnhub_client = start_mcp(
            self.runtime, "finnhub-fundamentals-data-server", env_file=True
        )

    def _init_session_manager(self) -> None:
        self.session_manager = self.runtime.session_for("fundamentals_analyst")

    def _init_tools(self) -> None:
        self.tools = (
            self.stdio_mcp_simfin_client.list_tools_sync()
            + self.stdio_mcp_finnhub_client.list_tools_sync()
        )

    def _init_hooks(self) -> None:
        self.lifecycle_hooks = SharedDocument(runtime=self.runtime, memory=None)
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def get_fundamentals_analyst_insights(self, message: str) -> AgentResult:
        """Get fundamentals analyst insights for investment decisions by requesting the analysis for ticker and date."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    run_example(FundamentalsAnalyst, "fundamentals_analyst_report")
