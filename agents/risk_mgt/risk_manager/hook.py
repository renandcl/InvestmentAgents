import json
import os
import re

from strands.hooks import (
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    HookProvider,
    HookRegistry,
)


class SharedDocument(HookProvider):
    def __init__(self, shared_document_json_file: str, memory):
        self.shared_document_file = shared_document_json_file
        self.memory = memory

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_document)
        registry.add_callback(BeforeModelCallEvent, self.add_prompt_reports)
        registry.add_callback(AfterInvocationEvent, self.save_shared_document)
        registry.add_callback(AfterModelCallEvent, self.risk_debate_history_after_model)
        registry.add_callback(AfterToolCallEvent, self.risk_debate_history_after_tool)

    def get_shared_document(self, event: BeforeInvocationEvent):
        event.agent.state.set("system_prompt", event.agent.system_prompt)

        if os.path.exists(self.shared_document_file):
            with open(self.shared_document_file, "r") as f:
                shared_document = json.load(f)
        else:
            shared_document = {}

        event.agent.state.set("current_date", shared_document.get("current_date"))
        event.agent.state.set("ticker", shared_document.get("ticker"))
        event.agent.state.set("shared_document_file", self.shared_document_file)

        event.agent.state.set(
            "fundamentals_analyst_report",
            shared_document.get("fundamentals_analyst_report"),
        )
        event.agent.state.set(
            "market_analyst_report", shared_document.get("market_analyst_report")
        )
        event.agent.state.set(
            "news_analyst_report", shared_document.get("news_analyst_report")
        )

        # Get trader's plan - try multiple field names for compatibility
        trader_investment_plan = shared_document.get(
            "trader_investment_plan", "No trader plan available"
        )
        event.agent.state.set("trader_investment_plan", trader_investment_plan)

        event.agent.state.set("debate_rounds", shared_document.get("debate_rounds", 0))
        event.agent.state.set(
            "debate_action",
            shared_document.get(
                "debate_action",
                "Call Aggressive, Neutral and Conservative Analysts to provide their analysis.",
            ),
        )

        past_memory_str = self._get_past_memories(shared_document)
        event.agent.state.set("past_memories", past_memory_str)

    def add_prompt_reports(self, event: BeforeModelCallEvent):
        system_prompt = event.agent.state.get("system_prompt")

        event.agent.system_prompt = system_prompt.format(
            trader_investment_plan=event.agent.state.get("trader_investment_plan"),
            risk_debate_history=event.agent.state.get("risk_debate_history"),
            past_memories=event.agent.state.get("past_memories"),
            debate_rounds=event.agent.state.get("debate_rounds"),
            debate_action=event.agent.state.get("debate_action"),
        )

        if "toolResponse" in event.agent.messages[-1]:
            event.agent.state.set(
                "debate_rounds", event.agent.state.get("debate_rounds") + 1
            )
            if event.agent.state.get("debate_rounds") >= 3:
                event.agent.state.set(
                    "debate_action",
                    "Make final risk-adjusted trading decision based on the analyses provided.",
                )
            else:
                event.agent.state.set(
                    "debate_action",
                    "Call Aggressive, Neutral and Conservative Analysts to debate on each other's analysis.",
                )

    def save_shared_document(self, event: AfterInvocationEvent):
        if os.path.exists(self.shared_document_file):
            with open(self.shared_document_file, "r") as f:
                shared_document = json.load(f)
        else:
            shared_document = {}

        message = event.agent.messages[-1]["content"][0]["text"]
        report_match = re.search(r"<think>(.*?)</think>(.*)", message, re.DOTALL)
        if report_match:
            report = report_match.group(2).strip()
        else:
            report = message

        event.agent.state.set(f"{event.agent.agent_id}_decision", report)
        shared_document[f"{event.agent.agent_id}_decision"] = report
        shared_document["final_trade_decision"] = report

        # Save to memory
        self.memory.add_memory(
            memory=f"Risk Manager Decision for {shared_document.get('ticker')}: {report}",
            ticker=shared_document.get("ticker"),
        )

        with open(self.shared_document_file, "w") as f:
            json.dump(shared_document, f, indent=2)

    def _get_past_memories(self, shared_document):
        current_situation = f"""
Date: {shared_document.get('current_date')}
Ticker: {shared_document.get('ticker')}
Market Research Report: {shared_document.get('market_analyst_report')}
Latest World Affairs News: {shared_document.get('news_analyst_report')}
Company Fundamentals Report: {shared_document.get('fundamentals_analyst_report')}
        """.strip()
        past_memories = self.memory.search_memories(
            current_situation, ticker=shared_document.get("ticker"), n_matches=2
        )

        records = []
        if isinstance(past_memories, dict):
            records = past_memories.get("results") or []
        elif isinstance(past_memories, list):
            records = past_memories

        if records:
            past_memory_str = ""
            for i, rec in enumerate(records, 1):
                memory_text = rec.get("memory") or rec.get("text")
                if not memory_text:
                    continue
                past_memory_str += f"Memory {i}:\n{memory_text}\n\n"
            return past_memory_str

        return "No relevant past memories found."

    def risk_debate_history_after_model(self, event: AfterModelCallEvent):
        # Get risk debate history
        event.agent.state.set("risk_debate_history", event.agent.messages)

    def risk_debate_history_after_tool(self, event: AfterToolCallEvent):
        event.agent.state.set("risk_debate_history", event.agent.messages)
