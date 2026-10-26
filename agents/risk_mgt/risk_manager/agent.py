from __future__ import annotations

import os
from typing import TYPE_CHECKING

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.debates.runner import DebateRunner
from agents.risk_mgt.aggressive_debator.agent import AggressiveDebator
from agents.risk_mgt.conservative_debator.agent import ConservativeDebator
from agents.risk_mgt.neutral_debator.agent import NeutralDebator
from agents.risk_mgt.risk_manager.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime
from runtime.examples import run_example

if TYPE_CHECKING:
    from runtime.lifecycle import RunRuntime


class RiskManager(Agent):
    def __init__(self, *, runtime: RunRuntime) -> None:
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_session_manager()
        self._init_hooks()
        self._init_tools()

        super().__init__(
            runtime=self.runtime,
            name="RiskManagerAgent",
            agent_id="risk_manager",
            description="Evaluates risk debate between aggressive, conservative, and neutral analysts to make final risk-adjusted trading decisions.",
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
        settings = self.runtime.config.model_for("RISK_MANAGERS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_session_manager(self) -> None:
        self.session_manager = self.runtime.session_for("risk_manager")

    def _init_hooks(self) -> None:
        self.lifecycle_hooks = SharedDocument(
            runtime=self.runtime, memory=self.runtime.memory_for("risk_manager")
        )
        self.hooks = [self.lifecycle_hooks]

    def _init_tools(self) -> None:
        aggressive_debator = AggressiveDebator(runtime=self.runtime)
        conservative_debator = ConservativeDebator(runtime=self.runtime)
        neutral_debator = NeutralDebator(runtime=self.runtime)
        self.lifecycle_hooks.debate_runner = DebateRunner(
            self.lifecycle_hooks.spec.workflow,
            {
                "aggressive_risk_analyst": aggressive_debator,
                "conservative_risk_analyst": conservative_debator,
                "neutral_risk_analyst": neutral_debator,
            },
            self.lifecycle_hooks.store,
        )
        self.tools = []

    @tool
    async def get_risk_manager_evaluation_and_decision(self, query: str) -> AgentResult:
        """
        Evaluates risk perspectives. Coordinates three risk analysts to debate, then synthesizes their arguments into a final risk-adjusted recommendation.
        """
        return await self.invoke_async(query)


if __name__ == "__main__":
    run_example(RiskManager, "risk_manager_report")
