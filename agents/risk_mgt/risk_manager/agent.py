import asyncio
import logging
import os
import uuid
from datetime import datetime

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

from memory import MemoryService
from hook import SharedDocument
from agents.risk_mgt.aggressive_debator.agent import AggressiveDebator
from agents.risk_mgt.conservative_debator.agent import ConservativeDebator
from agents.risk_mgt.neutral_debator.agent import NeutralDebator

# Enable debug logs
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class RiskManager:
    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        # Initialize the three risk debators
        aggressive_debator = AggressiveDebator()
        conservative_debator = ConservativeDebator()
        neutral_debator = NeutralDebator()

        # Load system prompt
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        current_date = datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/risk_mgt/risk_manager",
        )

        shared_document_file = "data/shared_document.json"
        memory = MemoryService(agent_id="risk_manager")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)

        self.agent = Agent(
            name="RiskManagerAgent",
            agent_id="risk_manager",
            description="Evaluates risk debate between aggressive, conservative, and neutral analysts to make final risk-adjusted trading decisions.",
            system_prompt=self.system_prompt,
            tools=[
                aggressive_debator.provide_aggressive_analysis,
                conservative_debator.provide_conservative_analysis,
                neutral_debator.provide_neutral_analysis,
            ],
            model=self.ollama_model,
            session_manager=self.session_manager,
            hooks=[
                shared_document_handler_hook.get_shared_document,
                shared_document_handler_hook.add_prompt_reports,
                shared_document_handler_hook.save_shared_document,
            ],
        )

    @tool
    async def evaluate_risk_and_decide(self, query: str) -> str:
        """
        Evaluates risk perspectives and makes final trading decision.
        
        Coordinates three risk analysts to debate, then synthesizes their
        arguments into a final risk-adjusted recommendation.
        
        Args:
            query: Request for risk evaluation and decision
            
        Returns:
            Final risk-adjusted trading decision (BUY/SELL/HOLD) with rationale
        """
        result: AgentResult = await self.agent.run(query)
        return result.data


# For testing
async def main():
    risk_manager = RiskManager()
    result = await risk_manager.evaluate_risk_and_decide(
        "Evaluate the trader's decision from all risk perspectives and provide your final risk-adjusted recommendation."
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
