import os

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.researchers.bull.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime


class BullResearcher(Agent):
    def __init__(self, *, runtime):
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_session_manager()
        self._init_hooks()

        super().__init__(
            runtime=self.runtime,
            name="BullResearcherAgent",
            agent_id="bull_researcher",
            description="Analyses bull market trends and provides insights.",
            system_prompt=self.system_prompt,
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
        settings = self.runtime.config.model_for("RESEARCHERS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_session_manager(self):
        self.session_manager = self.runtime.session_for("bull_researcher")

    def _init_hooks(self):
        self.lifecycle_hooks = SharedDocument(
            runtime=self.runtime, memory=self.runtime.memory_for("bull_researcher")
        )
        self.hooks = [self.lifecycle_hooks]

    @tool
    async def get_bull_researcher_insights(self, message: str) -> AgentResult:
        """Get insights from the bull market researcher. Make a query for bull analyst."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    from runtime.examples import run_example

    run_example(BullResearcher, "bull_researcher_report")
