import logging
import os

from strands import tool
from strands.agent import AgentResult
from strands.models.openai import OpenAIModel

from agents.debates.runner import DebateRunner
from agents.researchers.bear.agent import BearResearcher
from agents.researchers.bull.agent import BullResearcher
from agents.researchers.manager.hook import SharedDocument
from runtime.agent import RunAgent as Agent
from runtime.agent import require_runtime

# Enable debug logs and print them to stderr
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class ResearchManager(Agent):
    def __init__(self, *, runtime):
        self.runtime = require_runtime(runtime)
        self._init_system_prompt()
        self._init_model()
        self._init_session_manager()
        self._init_hooks()
        self._init_tools()

        super().__init__(
            runtime=self.runtime,
            name="ResearchManagerAgent",
            agent_id="research_manager",
            description="Critically evaluates research from both bull and bear analysts and makes an informed investment plan.",
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
        settings = self.runtime.config.model_for("RESEARCHERS")
        self.model = OpenAIModel(
            client_args={"base_url": settings.base_url, "api_key": settings.api_key},
            model_id=settings.model_id,
        )

    def _init_session_manager(self):
        self.session_manager = self.runtime.session_for("research_manager")

    def _init_hooks(self):
        self.lifecycle_hooks = SharedDocument(
            runtime=self.runtime, memory=self.runtime.memory_for("research_manager")
        )
        self.hooks = [self.lifecycle_hooks]

    def _init_tools(self):
        bear_researcher = BearResearcher(runtime=self.runtime)
        bull_researcher = BullResearcher(runtime=self.runtime)
        self.lifecycle_hooks.debate_runner = DebateRunner(
            self.lifecycle_hooks.spec.workflow,
            {"bull_researcher": bull_researcher, "bear_researcher": bear_researcher},
            self.lifecycle_hooks.store,
        )
        self.tools = []

    @tool
    async def get_research_manager_investment_plan(self, message: str) -> AgentResult:
        """Get researcher manager to critically evaluate the research from both bull and bear analysts and make an informed investment plan."""
        return await self.invoke_async(message)


if __name__ == "__main__":
    from runtime.examples import run_example

    run_example(ResearchManager, "research_manager_report")
