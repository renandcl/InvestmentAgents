"""
Shared State Handler for Aggressive Debator Agent

Manages state loading, prompt formatting, and state saving through hooks.
"""

import json
import os
from datetime import datetime

from strands import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    BeforeModelInvocationEvent,
)


class SharedDocument:
    """Handles shared state management for the Aggressive Debator agent via hooks."""

    def __init__(self, memory_service):
        """
        Initialize the state handler.

        Args:
            memory_service: Memory service for retrieving past trading memories
        """
        self.memory_service = memory_service
        self.shared_document = {}
        self.state_file = "data/shared_document.json"

    def get_shared_document(self, event: BeforeInvocationEvent):
        """
        Hook 1: Load shared state before agent invocation.

        Loads:
        - ticker, current_date
        - market_report, news_report, fundamentals_report
        - trader_decision (from trader or trader_report)
        - risk_debate_history and individual analyst arguments
        """
        # Load shared state from file
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                self.shared_document = json.load(f)
        else:
            self.shared_document = {}

        # Store in event context
        event.context["ticker"] = self.shared_document.get("ticker", "UNKNOWN")
        event.context["current_date"] = self.shared_document.get(
            "current_date", datetime.now().strftime("%Y-%m-%d")
        )
        event.context["market_report"] = self.shared_document.get(
            "market_report", "No market report available."
        )
        event.context["news_report"] = self.shared_document.get(
            "news_report", "No news report available."
        )
        event.context["fundamentals_report"] = self.shared_document.get(
            "fundamentals_report", "No fundamentals report available."
        )

        # Trader's decision - try trader_investment_plan first (TradingAgents pattern), then fallbacks
        event.context["trader_decision"] = self.shared_document.get(
            "trader_investment_plan",
            self.shared_document.get(
                "trader_decision",
                self.shared_document.get(
                    "trader_report", "No trader decision available."
                ),
            ),
        )

        # Risk debate context - following TradingAgents RiskDebateState pattern
        risk_debate = self.shared_document.get("risk_debate_state", {})
        event.context["risk_debate_history"] = risk_debate.get(
            "history", "No debate history yet."
        )
        event.context["conservative_argument"] = risk_debate.get(
            "current_safe_response", "No conservative argument yet."
        )
        event.context["neutral_argument"] = risk_debate.get(
            "current_neutral_response", "No neutral argument yet."
        )

        # Get relevant past memories
        curr_situation = f"{event.context['market_report']}\n\n{event.context['news_report']}\n\n{event.context['fundamentals_report']}"
        memories = self.memory_service.search_memories(curr_situation, n_results=3)

        if memories and len(memories) > 0:
            memories_text = "\n\n".join(
                [f"Memory {i+1}:\n{mem['text']}" for i, mem in enumerate(memories)]
            )
        else:
            memories_text = "No relevant past memories available."

        event.context["past_memories"] = memories_text

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
        """
        Hook 2: Format system prompt with actual data before model invocation.
        """
        event.agent.system_prompt = event.agent.system_prompt.format(
            ticker=event.context.get("ticker", "UNKNOWN"),
            current_date=event.context.get("current_date", "UNKNOWN"),
            market_report=event.context.get("market_report", "No data"),
            news_report=event.context.get("news_report", "No data"),
            fundamentals_report=event.context.get("fundamentals_report", "No data"),
            trader_decision=event.context.get(
                "trader_decision", "No decision available"
            ),
            risk_debate_history=event.context.get(
                "risk_debate_history", "No debate yet"
            ),
            conservative_argument=event.context.get(
                "conservative_argument", "None yet"
            ),
            neutral_argument=event.context.get("neutral_argument", "None yet"),
            past_memories=event.context.get("past_memories", "No memories"),
        )

    def save_shared_document(self, event: AfterInvocationEvent):
        """
        Hook 3: Save aggressive analysis to shared state after agent execution.
        Follows TradingAgents RiskDebateState pattern.
        """
        # Get the agent's response
        aggressive_analysis = event.result

        # Update risk_debate_state in shared state (following TradingAgents pattern)
        if "risk_debate_state" not in self.shared_document:
            self.shared_document["risk_debate_state"] = {
                "history": "",
                "risky_history": "",
                "safe_history": "",
                "neutral_history": "",
                "latest_speaker": "",
                "current_risky_response": "",
                "current_safe_response": "",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 0,
            }

        risk_debate_state = self.shared_document["risk_debate_state"]

        # Format argument with analyst prefix (matching TradingAgents pattern)
        argument = f"Risky Analyst: {aggressive_analysis}"

        # Update debate state
        risk_debate_state["history"] = (
            risk_debate_state.get("history", "") + "\n" + argument
        )
        risk_debate_state["risky_history"] = (
            risk_debate_state.get("risky_history", "") + "\n" + argument
        )
        risk_debate_state["latest_speaker"] = "Risky"
        risk_debate_state["current_risky_response"] = argument
        risk_debate_state["count"] = risk_debate_state.get("count", 0) + 1

        self.shared_document["risk_debate_state"] = risk_debate_state

        # Also save direct field for convenience
        self.shared_document["aggressive_analysis"] = aggressive_analysis

        # Save to memory for learning
        self.memory_service.add_memory(
            text=f"Aggressive Analysis: {aggressive_analysis}",
            metadata={
                "ticker": self.shared_document.get("ticker"),
                "date": self.shared_document.get("current_date"),
                "type": "aggressive_risk_analysis",
            },
        )

        # Save shared state to file
        os.makedirs("data", exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.shared_document, f, indent=2)
