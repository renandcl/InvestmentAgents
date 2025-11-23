import json
import os
import re

from strands.experimental.hooks import BeforeModelInvocationEvent
from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    HookProvider,
    HookRegistry,
)


class SharedDocument(HookProvider):
    def __init__(self, shared_document_json_file: str, memory):
        self.shared_document_file = shared_document_json_file
        self.memory = memory

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_document)
        registry.add_callback(BeforeModelInvocationEvent, self.add_prompt_reports)
        registry.add_callback(AfterInvocationEvent, self.save_shared_document)

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
            "fundamentals_report", shared_document.get("fundamentals_report")
        )
        event.agent.state.set("market_report", shared_document.get("market_report"))
        event.agent.state.set("news_report", shared_document.get("news_report"))

        # Get trader's plan - try multiple field names for compatibility
        trader_investment_plan = shared_document.get(
            "trader_investment_plan", "No trader plan available"
        )
        event.agent.state.set("trader_investment_plan", trader_investment_plan)

        # Get risk debate history
        # The prompt expects {history}, so we map risk_debate_state['history'] to it.
        risk_debate = shared_document.get("risk_debate_state", {})
        risk_debate_history = risk_debate.get("history", "No debate history yet")
        event.agent.state.set("history", risk_debate_history)

        past_memory_str = self._get_past_memories(shared_document)
        event.agent.state.set("past_memories", past_memory_str)

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
        system_prompt = event.agent.state.get("system_prompt")

        event.agent.system_prompt = system_prompt.format(
            trader_investment_plan=event.agent.state.get("trader_investment_plan"),
            history=event.agent.state.get("history"),
            past_memories=event.agent.state.get("past_memories"),
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
Market Research Report: {shared_document.get('market_report')}
Latest World Affairs News: {shared_document.get('news_report')}
Company Fundamentals Report: {shared_document.get('fundamentals_report')}
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
