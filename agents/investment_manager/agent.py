"""
Investment Manager Agent

Main orchestrator that coordinates the entire investment decision workflow.
Sequences: Analysts → Research → Trading → Risk Management → Execution
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime

from hook import SharedDocument
from memory import MemoryService
from strands import Agent, tool
from strands.models.ollama import OllamaModel
from strands.session.file_session_manager import FileSessionManager

# Import coordinator agents for direct invocation (testing/development)
from agents.analysts.analysts_coordinator.agent import AnalystCoordinator
from agents.researchers.manager.agent import ResearchManager
from agents.risk_mgt.risk_manager.agent import RiskManager
from agents.traders.trader.agent import Trader

# Enable debug logs
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)


class InvestmentManager:
    """
    Investment Manager - Main System Orchestrator

    Coordinates the complete investment decision workflow:
    1. Analysis Phase: Analysts Coordinator gathers market intelligence
    2. Research Phase: Research Manager evaluates bull/bear perspectives
    3. Trading Phase: Trader develops execution plan
    4. Risk Phase: Risk Manager evaluates and makes final decision
    5. Execution: Investment Manager approves/rejects execution
    """

    def __init__(self, model_id="qwen3:8b", host="http://localhost:11434"):
        self.model_id = model_id
        self.host = host

        self.ollama_model = OllamaModel(
            host=self.host,
            model_id=self.model_id,
        )

        # Initialize coordinator agents
        self.analyst_coordinator = AnalystCoordinator()
        self.research_manager = ResearchManager()
        self.trader = Trader()
        self.risk_manager = RiskManager()

        # Load system prompt
        with open(os.path.join(os.path.dirname(__file__), "prompt.txt"), "r") as f:
            self.system_prompt = f.read()

        current_date = datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.session_manager = FileSessionManager(
            session_id=f"{current_date}_{uuid.uuid4()}",
            storage_dir="data/agents_sessions/investment_manager",
        )

        shared_document_file = "data/shared_document.json"
        memory = MemoryService(agent_id="investment_manager")
        shared_document_handler_hook = SharedDocument(shared_document_file, memory)

        self.agent = Agent(
            name="InvestmentManagerAgent",
            agent_id="investment_manager",
            description="Main orchestrator that coordinates the complete investment decision workflow across all agents",
            system_prompt=self.system_prompt,
            tools=[
                self.execute_analysis_phase,
                self.execute_research_phase,
                self.execute_trading_phase,
                self.execute_risk_phase,
                self.make_execution_decision,
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
    async def execute_analysis_phase(self, ticker: str, date: str = None) -> str:
        """
        Phase 1: Execute market analysis by coordinating all analysts.

        Calls the Analysts Coordinator to gather:
        - Fundamentals analysis
        - News analysis
        - Market technical analysis

        Args:
            ticker: Stock ticker symbol
            date: Analysis date (defaults to today)

        Returns:
            Summary of analysis phase completion
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logging.info(f"=== PHASE 1: ANALYSIS - Starting for {ticker} on {date} ===")

        # Initialize shared state
        shared_document = {
            "ticker": ticker,
            "current_date": date,
            "phase": "analysis",
        }

        os.makedirs("data", exist_ok=True)
        with open("data/shared_document.json", "w") as f:
            json.dump(shared_document, f, indent=2)

        # Call analysts coordinator
        query = (
            f"Analyze {ticker} for {date}. Provide comprehensive market intelligence."
        )
        result = await self.analyst_coordinator.get_analysts_insights(query)

        logging.info("=== PHASE 1: ANALYSIS - Completed ===")
        return f"Analysis phase completed for {ticker}. Reports generated: fundamentals, news, market."

    @tool
    async def execute_research_phase(self, query: str) -> str:
        """
        Phase 2: Execute research by evaluating bull and bear perspectives.

        Calls the Research Manager to:
        - Generate bull case analysis
        - Generate bear case analysis
        - Synthesize investment recommendation

        Args:
            query: Research request

        Returns:
            Summary of research phase completion
        """
        logging.info("=== PHASE 2: RESEARCH - Starting ===")

        # Update phase in shared state
        with open("data/shared_document.json", "r") as f:
            shared_document = json.load(f)
        shared_document["phase"] = "research"
        with open("data/shared_document.json", "w") as f:
            json.dump(shared_document, f, indent=2)

        # Call research manager
        result = await self.research_manager.get_research_manager_investment_plan(query)

        logging.info("=== PHASE 2: RESEARCH - Completed ===")
        return "Research phase completed. Investment plan and recommendation generated."

    @tool
    async def execute_trading_phase(self, query: str) -> str:
        """
        Phase 3: Execute trading plan development.

        Calls the Trader to:
        - Review investment recommendation
        - Develop specific execution plan
        - Define risk parameters (entry, exit, stop-loss)

        Args:
            query: Trading request

        Returns:
            Summary of trading phase completion
        """
        logging.info("=== PHASE 3: TRADING - Starting ===")

        # Update phase in shared state
        with open("data/shared_document.json", "r") as f:
            shared_document = json.load(f)
        shared_document["phase"] = "trading"
        with open("data/shared_document.json", "w") as f:
            json.dump(shared_document, f, indent=2)

        # Call trader
        result = await self.trader.get_trader_investment_decision(query)

        logging.info("=== PHASE 3: TRADING - Completed ===")
        return "Trading phase completed. Execution plan with risk parameters generated."

    @tool
    async def execute_risk_phase(self, query: str) -> str:
        """
        Phase 4: Execute risk management evaluation and final decision.

        Calls the Risk Manager to:
        - Coordinate risk debate (aggressive, conservative, neutral)
        - Evaluate all perspectives
        - Make final risk-adjusted decision (BUY/SELL/HOLD)

        Args:
            query: Risk evaluation request

        Returns:
            Summary of risk phase completion with final decision
        """
        logging.info("=== PHASE 4: RISK MANAGEMENT - Starting ===")

        # Update phase in shared state
        with open("data/shared_document.json", "r") as f:
            shared_document = json.load(f)
        shared_document["phase"] = "risk_management"
        with open("data/shared_document.json", "w") as f:
            json.dump(shared_document, f, indent=2)

        # Call risk manager
        result = await self.risk_manager.evaluate_risk_and_decide(query)

        logging.info("=== PHASE 4: RISK MANAGEMENT - Completed ===")

        # Get final decision from shared state
        with open("data/shared_document.json", "r") as f:
            shared_document = json.load(f)

        final_decision = shared_document.get(
            "final_trade_decision", "No decision found"
        )
        return f"Risk management phase completed. Final decision: {final_decision[:200]}..."

    @tool
    async def make_execution_decision(self, review_decision: bool = True) -> str:
        """
        Phase 5: Make final execution decision (GO/NO-GO).

        Reviews the final_trade_decision from Risk Manager and approves/rejects
        for actual execution.

        Args:
            review_decision: Whether to review before approving (default True)

        Returns:
            Execution decision with rationale
        """
        logging.info("=== PHASE 5: EXECUTION DECISION - Starting ===")

        # Load final decision
        with open("data/shared_document.json", "r") as f:
            shared_document = json.load(f)

        ticker = shared_document.get("ticker", "UNKNOWN")
        final_decision = shared_document.get("final_trade_decision", "No decision")
        risk_debate = shared_document.get("risk_debate_state", {})

        # Extract BUY/SELL/HOLD from decision
        decision_upper = final_decision.upper()
        if (
            "BUY" in decision_upper
            and "SELL" not in decision_upper[: decision_upper.find("BUY") + 10]
        ):
            action = "BUY"
            execution_status = "APPROVED"
        elif "SELL" in decision_upper:
            action = "SELL"
            execution_status = "APPROVED"
        elif "HOLD" in decision_upper:
            action = "HOLD"
            execution_status = "HOLD"
        else:
            action = "UNCLEAR"
            execution_status = "REJECTED"

        # Save execution decision
        shared_document["execution_action"] = action
        shared_document["execution_status"] = execution_status
        shared_document["phase"] = "completed"

        with open("data/shared_document.json", "w") as f:
            json.dump(shared_document, f, indent=2)

        logging.info(f"=== PHASE 5: EXECUTION DECISION - {execution_status} ===")

        return f"Execution Decision for {ticker}: {action} - {execution_status}\n\nRationale: Based on comprehensive risk-adjusted analysis across all perspectives."

    async def run_complete_workflow(self, ticker: str, date: str = None) -> dict:
        """
        Execute the complete investment decision workflow.

        Runs all phases sequentially:
        1. Analysis
        2. Research
        3. Trading
        4. Risk Management
        5. Execution Decision

        Args:
            ticker: Stock ticker symbol
            date: Analysis date (defaults to today)

        Returns:
            Dictionary with workflow results
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logging.info(f"\n{'='*60}")
        logging.info(f"INVESTMENT WORKFLOW STARTING: {ticker} on {date}")
        logging.info(f"{'='*60}\n")

        try:
            # Phase 1: Analysis
            analysis_result = await self.execute_analysis_phase(ticker, date)

            # Phase 2: Research
            research_result = await self.execute_research_phase(
                f"Evaluate investment opportunity for {ticker} based on analyst reports."
            )

            # Phase 3: Trading
            trading_result = await self.execute_trading_phase(
                f"Develop trading execution plan for {ticker} based on research recommendation."
            )

            # Phase 4: Risk Management
            risk_result = await self.execute_risk_phase(
                f"Evaluate trading plan for {ticker} from all risk perspectives and provide final decision."
            )

            # Phase 5: Execution Decision
            execution_result = await self.make_execution_decision()

            # Load final state
            with open("data/shared_document.json", "r") as f:
                final_state = json.load(f)

            logging.info(f"\n{'='*60}")
            logging.info(f"INVESTMENT WORKFLOW COMPLETED: {ticker}")
            logging.info(f"Final Action: {final_state.get('execution_action')}")
            logging.info(f"Status: {final_state.get('execution_status')}")
            logging.info(f"{'='*60}\n")

            return {
                "ticker": ticker,
                "date": date,
                "execution_action": final_state.get("execution_action"),
                "execution_status": final_state.get("execution_status"),
                "phases": {
                    "analysis": analysis_result,
                    "research": research_result,
                    "trading": trading_result,
                    "risk": risk_result,
                    "execution": execution_result,
                },
                "final_state": final_state,
            }

        except Exception as e:
            logging.error(f"Workflow failed: {str(e)}")
            raise


# For testing
async def main():
    manager = InvestmentManager()

    # Run complete workflow
    result = await manager.run_complete_workflow("AAPL", "2025-10-12")

    print("\n" + "=" * 60)
    print("WORKFLOW RESULT:")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
