import json
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
        with open(self.shared_document_file, "r") as f:
            shared_document = json.load(f)

        event.agent.state.set("current_date", shared_document.get("current_date"))
        event.agent.state.set("ticker", shared_document.get("ticker"))
        event.agent.state.set("shared_document_file", self.shared_document_file)

        # Get all analyst reports
        event.agent.state.set(
            "fundamentals_report", shared_document.get("fundamentals_report")
        )
        event.agent.state.set("market_report", shared_document.get("market_report"))
        event.agent.state.set("news_report", shared_document.get("news_report"))

        # Get research outputs
        investment_plan = shared_document.get(
            "investment_plan", "No investment plan provided"
        )
        judge_decision = shared_document.get("judge_decision", "No decision provided")

        event.agent.state.set("investment_plan", investment_plan)
        event.agent.state.set("judge_decision", judge_decision)

        # Get past trading memories
        past_memory_str = self._get_past_memories(shared_document)
        event.agent.state.set("past_memories", past_memory_str)

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
        event.agent.system_prompt = event.agent.system_prompt.format(
            ticker=event.agent.state.get("ticker"),
            date=event.agent.state.get("current_date"),
            fundamentals_report=event.agent.state.get("fundamentals_report"),
            market_report=event.agent.state.get("market_report"),
            news_report=event.agent.state.get("news_report"),
            investment_plan=event.agent.state.get("investment_plan"),
            judge_decision=event.agent.state.get("judge_decision"),
            past_memories=event.agent.state.get("past_memories"),
        )

    def save_shared_document(self, event: AfterInvocationEvent):
        with open(self.shared_document_file, "r") as f:
            shared_document = json.load(f)

        message = event.agent.messages[-1]["content"][0]["text"]
        report_match = re.search(r"<think>(.*?)</think>(.*)", message, re.DOTALL)
        if report_match:
            report = report_match.group(2).strip()
            event.agent.state.set(f"{event.agent.agent_id}_report", report)
            shared_document[f"{event.agent.agent_id}_report"] = report
        else:
            event.agent.state.set(f"{event.agent.agent_id}_report", message)
            shared_document[f"{event.agent.agent_id}_report"] = message

        # Also save as trader_investment_plan for compatibility with TradingAgents
        shared_document["trader_investment_plan"] = message
        shared_document["trader_decision"] = message

        with open(self.shared_document_file, "w") as f:
            json.dump(shared_document, f)

    def _get_past_memories(self, shared_document):
        current_situation = f"""
Date: {shared_document.get('current_date')}
Ticker: {shared_document.get('ticker')}
Market Research Report: {shared_document.get('market_report')}
Latest World Affairs News: {shared_document.get('news_report')}
Company Fundamentals Report: {shared_document.get('fundamentals_report')}
Investment Plan: {shared_document.get('investment_plan')}
        """.strip()
        past_memories = self.memory.search_memories(
            current_situation, ticker=shared_document.get("ticker"), n_matches=2
        )
        if past_memories:
            past_memory_str = ""
            for i, rec in enumerate(past_memories["results"], 1):
                past_memory_str += rec["text"] + "\n\n"
            return past_memory_str
        else:
            return "No relevant past trading decisions found."
