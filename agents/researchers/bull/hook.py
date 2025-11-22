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
    def __init__(self, shared_document_file: str, memory):
        self.shared_document_file = shared_document_file
        self.memory = memory

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_document)
        registry.add_callback(BeforeModelInvocationEvent, self.add_prompt_reports)
        registry.add_callback(AfterInvocationEvent, self.save_shared_document)

    def get_shared_document(self, event: BeforeInvocationEvent):
        event.agent.state.set("system_prompt", event.agent.system_prompt)
        with open(self.shared_document_file, "r") as f:
            shared_document = json.load(f)

        event.agent.state.set("current_date", shared_document.get("current_date"))
        event.agent.state.set("ticker", shared_document.get("ticker"))
        event.agent.state.set("shared_document_file", self.shared_document_file)

        event.agent.state.set(
            "fundamentals_report", shared_document.get("fundamentals_report")
        )
        event.agent.state.set("market_report", shared_document.get("market_report"))
        event.agent.state.set("news_report", shared_document.get("news_report"))

        if "bull_researcher_report" in shared_document:
            report = (
                shared_document.get("bull_researcher_report")
                if shared_document.get("bull_researcher_report")
                else "No report"
            )
            event.agent.state.set("bull_researcher_report", report)
        if "bear_researcher_report" in shared_document:
            report = (
                shared_document.get("bear_researcher_report")
                if shared_document.get("bear_researcher_report")
                else "No report"
            )
            event.agent.state.set("bear_researcher_report", report)

        past_memory_str = self._get_past_memories(shared_document)
        event.agent.state.set("past_memories", past_memory_str)

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
        system_prompt = event.agent.state.get("system_prompt")
        event.agent.system_prompt = system_prompt.format(
            ticker=event.agent.state.get("ticker"),
            date=event.agent.state.get("current_date"),
            fundamentals_report=event.agent.state.get("fundamentals_report"),
            market_report=event.agent.state.get("market_report"),
            news_report=event.agent.state.get("news_report"),
            bear_researcher_report=event.agent.state.get("bear_researcher_report"),
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

        with open(self.shared_document_file, "w") as f:
            json.dump(shared_document, f)

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
            for rec in records:
                memory_text = rec.get("memory") or rec.get("text")
                if not memory_text:
                    continue
                past_memory_str += memory_text + "\n\n"
            if past_memory_str:
                return past_memory_str

        return "No relevant past memories found."
