import json
import re

from strands.experimental.hooks import BeforeModelInvocationEvent
from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    HookProvider,
    HookRegistry,
)


class SharedStateHandler(HookProvider):
    def __init__(self, shared_state_json_file: str, memory):
        self.shared_state_file = shared_state_json_file
        self.memory = memory

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_state)
        registry.add_callback(BeforeModelInvocationEvent, self.add_prompt_reports)
        registry.add_callback(AfterInvocationEvent, self.save_shared_state)

    def get_shared_state(self, event: BeforeInvocationEvent):
        with open(self.shared_state_file, "r") as f:
            shared_state = json.load(f)

        event.agent.state.set("current_date", shared_state.get("current_date"))
        event.agent.state.set("ticker", shared_state.get("ticker"))
        event.agent.state.set("shared_state_file", self.shared_state_file)

        event.agent.state.set(
            "fundamentals_report", shared_state.get("fundamentals_report")
        )
        event.agent.state.set("market_report", shared_state.get("market_report"))
        event.agent.state.set("news_report", shared_state.get("news_report"))

        # Get trader's plan - try multiple field names for compatibility
        trader_plan = shared_state.get("trader_investment_plan",
                                      shared_state.get("trader_decision",
                                      shared_state.get("trader_report", "No trader plan available")))
        event.agent.state.set("trader_plan", trader_plan)

        # Get risk debate history
        risk_debate_state = shared_state.get("risk_debate_state", {})
        risk_debate_history = risk_debate_state.get("history", "No debate history yet")
        event.agent.state.set("risk_debate_history", risk_debate_history)

        past_memory_str = self._get_past_memories(shared_state)
        event.agent.state.set("past_memories", past_memory_str)

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
        event.agent.system_prompt = event.agent.system_prompt.format(
            ticker=event.agent.state.get("ticker"),
            current_date=event.agent.state.get("current_date"),
            fundamentals_report=event.agent.state.get("fundamentals_report"),
            market_report=event.agent.state.get("market_report"),
            news_report=event.agent.state.get("news_report"),
            trader_plan=event.agent.state.get("trader_plan"),
            risk_debate_history=event.agent.state.get("risk_debate_history"),
            past_memories=event.agent.state.get("past_memories"),
        )

    def save_shared_state(self, event: AfterInvocationEvent):
        with open(self.shared_state_file, "r") as f:
            shared_state = json.load(f)

        message = event.agent.messages[-1]["content"][0]["text"]
        report_match = re.search(r"<think>(.*?)</think>(.*)", message, re.DOTALL)
        if report_match:
            report = report_match.group(2).strip()
            event.agent.state.set(f"{event.agent.agent_id}_decision", report)
            shared_state[f"{event.agent.agent_id}_decision"] = report
            # Also save to risk_debate_state for TradingAgents compatibility
            if "risk_debate_state" not in shared_state:
                shared_state["risk_debate_state"] = {}
            shared_state["risk_debate_state"]["judge_decision"] = report
            shared_state["final_trade_decision"] = report
        else:
            event.agent.state.set(f"{event.agent.agent_id}_decision", message)
            shared_state[f"{event.agent.agent_id}_decision"] = message
            if "risk_debate_state" not in shared_state:
                shared_state["risk_debate_state"] = {}
            shared_state["risk_debate_state"]["judge_decision"] = message
            shared_state["final_trade_decision"] = message

        with open(self.shared_state_file, "w") as f:
            json.dump(shared_state, f)

    def _get_past_memories(self, shared_state):
        current_situation = f"""
Date: {shared_state.get('current_date')}
Ticker: {shared_state.get('ticker')}
Market Research Report: {shared_state.get('market_report')}
Latest World Affairs News: {shared_state.get('news_report')}
Company Fundamentals Report: {shared_state.get('fundamentals_report')}
Bull Researcher Analysis: {shared_state.get('bull_researcher_report')}
Bear Researcher Analysis: {shared_state.get('bear_researcher_report')}
        """.strip()
        past_memories = self.memory.search_memories(
            current_situation, ticker=shared_state.get("ticker"), n_matches=2
        )
        if past_memories:
            past_memory_str = ""
            for i, rec in enumerate(past_memories["results"], 1):
                past_memory_str += rec["text"] + "\n\n"
            return past_memory_str
        else:
            return "No relevant past memories found."
