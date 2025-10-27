"""
Investment Manager Hook

Manages workflow state transitions and execution decisions.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from strands.hook import (
    BeforeInvocationEvent,
    BeforeModelInvocationEvent,
    AfterInvocationEvent,
)

if TYPE_CHECKING:
    from memory import MemoryService

logger = logging.getLogger(__name__)


class SharedDocument:
    """
    Hook handler for Investment Manager workflow state management.
    
    Manages:
    - Workflow initialization and phase transitions
    - State loading before each phase
    - Report aggregation for context
    - Execution decision saving
    """

    def __init__(self, shared_document_file: str, memory: "MemoryService"):
        self.shared_document_file = Path(shared_document_file)
        self.memory = memory

    def get_shared_document(self, event: BeforeInvocationEvent) -> None:
        """
        Load current workflow state at the start of invocation.
        
        Loads:
        - Ticker and date
        - Current phase
        - All phase results
        - Final decisions from previous phases
        """
        if not self.shared_document_file.exists():
            logger.info("No shared state file found - new workflow")
            return

        try:
            with open(self.shared_document_file, "r") as f:
                shared_document = json.load(f)

            # Extract key workflow info
            ticker = shared_document.get("ticker", "N/A")
            current_date = shared_document.get("current_date", "N/A")
            phase = shared_document.get("phase", "initialization")
            
            # Get reports from each phase
            fundamentals_report = shared_document.get("fundamentals_report", "")
            news_report = shared_document.get("news_report", "")
            market_report = shared_document.get("market_report", "")
            
            investment_plan = shared_document.get("investment_plan", "")
            investment_recommendation = shared_document.get("investment_recommendation", "")
            
            trader_plan = shared_document.get("trader_plan", "")
            
            final_trade_decision = shared_document.get("final_trade_decision", "")
            
            execution_action = shared_document.get("execution_action", "")
            execution_status = shared_document.get("execution_status", "")

            # Store in event
            event.shared_document = {
                "ticker": ticker,
                "current_date": current_date,
                "phase": phase,
                "fundamentals_report": fundamentals_report[:500] if fundamentals_report else "",
                "news_report": news_report[:500] if news_report else "",
                "market_report": market_report[:500] if market_report else "",
                "investment_plan": investment_plan[:500] if investment_plan else "",
                "investment_recommendation": investment_recommendation[:500] if investment_recommendation else "",
                "trader_plan": trader_plan[:500] if trader_plan else "",
                "final_trade_decision": final_trade_decision[:500] if final_trade_decision else "",
                "execution_action": execution_action,
                "execution_status": execution_status,
            }

            logger.info(f"Loaded workflow state: {ticker} - Phase: {phase}")

        except Exception as e:
            logger.error(f"Error loading shared state: {e}")

    def add_prompt_reports(self, event: BeforeModelInvocationEvent) -> None:
        """
        Add relevant reports to the model prompt based on current phase.
        
        Provides context from completed phases to inform current phase decisions.
        """
        shared_document = getattr(event, "shared_document", {})
        if not shared_document:
            return

        ticker = shared_document.get("ticker", "N/A")
        current_date = shared_document.get("current_date", "N/A")
        phase = shared_document.get("phase", "initialization")

        # Build context from completed phases
        context_parts = [
            f"\n{'='*60}",
            f"INVESTMENT WORKFLOW CONTEXT",
            f"{'='*60}",
            f"Ticker: {ticker}",
            f"Date: {current_date}",
            f"Current Phase: {phase}",
            f"{'='*60}\n",
        ]

        # Add phase-specific context
        if phase in ["research", "trading", "risk_management", "execution"]:
            # Analysis phase completed
            fundamentals = shared_document.get("fundamentals_report", "")
            news = shared_document.get("news_report", "")
            market = shared_document.get("market_report", "")
            
            if fundamentals or news or market:
                context_parts.append("\n--- ANALYSIS PHASE RESULTS ---")
                if fundamentals:
                    context_parts.append(f"Fundamentals: {fundamentals}")
                if news:
                    context_parts.append(f"News: {news}")
                if market:
                    context_parts.append(f"Market: {market}")

        if phase in ["trading", "risk_management", "execution"]:
            # Research phase completed
            plan = shared_document.get("investment_plan", "")
            recommendation = shared_document.get("investment_recommendation", "")
            
            if plan or recommendation:
                context_parts.append("\n--- RESEARCH PHASE RESULTS ---")
                if plan:
                    context_parts.append(f"Investment Plan: {plan}")
                if recommendation:
                    context_parts.append(f"Recommendation: {recommendation}")

        if phase in ["risk_management", "execution"]:
            # Trading phase completed
            trader_plan = shared_document.get("trader_plan", "")
            
            if trader_plan:
                context_parts.append("\n--- TRADING PHASE RESULTS ---")
                context_parts.append(f"Trader Plan: {trader_plan}")

        if phase == "execution":
            # Risk phase completed
            final_decision = shared_document.get("final_trade_decision", "")
            
            if final_decision:
                context_parts.append("\n--- RISK MANAGEMENT PHASE RESULTS ---")
                context_parts.append(f"Final Decision: {final_decision}")

        context_parts.append(f"\n{'='*60}\n")

        # Add to prompt
        context_text = "\n".join(context_parts)
        event.prompt.user_message.content = context_text + "\n\n" + event.prompt.user_message.content

        logger.info(f"Added workflow context for phase: {phase}")

    def save_shared_document(self, event: AfterInvocationEvent) -> None:
        """
        Save execution decision after workflow completion.
        
        Captures final execution decision and status.
        """
        try:
            # Load current state
            if self.shared_document_file.exists():
                with open(self.shared_document_file, "r") as f:
                    shared_document = json.load(f)
            else:
                shared_document = {}

            # Extract execution decision from response if present
            response_text = event.response.text if event.response else ""
            
            # Check if this is an execution decision
            if "execution decision" in response_text.lower() or "execution_action" in response_text.lower():
                # Parse action and status
                if "BUY" in response_text.upper():
                    shared_document["execution_action"] = "BUY"
                    shared_document["execution_status"] = "APPROVED"
                elif "SELL" in response_text.upper():
                    shared_document["execution_action"] = "SELL"
                    shared_document["execution_status"] = "APPROVED"
                elif "HOLD" in response_text.upper():
                    shared_document["execution_action"] = "HOLD"
                    shared_document["execution_status"] = "HOLD"
                
                shared_document["execution_decision_details"] = response_text[:1000]
                shared_document["phase"] = "completed"
                
                logger.info(f"Saved execution decision: {shared_document.get('execution_action')}")

            # Save state
            self.shared_document_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.shared_document_file, "w") as f:
                json.dump(shared_document, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving execution decision: {e}")
