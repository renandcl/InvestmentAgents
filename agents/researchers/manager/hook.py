import json
import re

from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    HookProvider,
    HookRegistry,
)


class SharedDocument(HookProvider):
    def __init__(self, shared_document_file: str, memory):
        self.shared_document_file = shared_document_file
        self.memory = memory

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_document)
        registry.add_callback(BeforeModelCallEvent, self.add_prompt_arguments)
        registry.add_callback(AfterInvocationEvent, self.save_shared_document)

    def get_shared_document(self, event: BeforeInvocationEvent):
        event.agent.state.set("system_prompt", event.agent.system_prompt)
        with open(self.shared_document_file, "r") as f:
            shared_document = json.load(f)

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

        # Get bull and bear researcher reports
        bull_researcher_report = shared_document.get(
            "bull_researcher_report", "No report"
        )
        bear_researcher_report = shared_document.get(
            "bear_researcher_report", "No report"
        )

        event.agent.state.set("bull_researcher_report", bull_researcher_report)
        event.agent.state.set("bear_researcher_report", bear_researcher_report)

        event.agent.state.set("debate_rounds", shared_document.get("debate_rounds", 0))
        event.agent.state.set(
            "debate_action",
            shared_document.get(
                "debate_action",
                "Call Bull and Bear Researchers to provide their analysis.",
            ),
        )

        past_memory_str = self._get_past_memories(shared_document)
        event.agent.state.set("past_memories", past_memory_str)

    def add_prompt_arguments(self, event: BeforeModelCallEvent):
        system_prompt = event.agent.state.get("system_prompt")
        event.agent.system_prompt = system_prompt.format(
            ticker=event.agent.state.get("ticker"),
            date=event.agent.state.get("current_date"),
            fundamentals_analyst_report=event.agent.state.get(
                "fundamentals_analyst_report"
            ),
            market_analyst_report=event.agent.state.get("market_analyst_report"),
            news_analyst_report=event.agent.state.get("news_analyst_report"),
            bull_researcher_report=event.agent.state.get("bull_researcher_report"),
            bear_researcher_report=event.agent.state.get("bear_researcher_report"),
            debate_rounds=event.agent.state.get("debate_rounds"),
            debate_action=event.agent.state.get("debate_action"),
            past_memories=event.agent.state.get("past_memories"),
        )

        if "toolResponse" in event.agent.messages[-1]:
            event.agent.state.set(
                "debate_rounds", event.agent.state.get("debate_rounds") + 1
            )
            if event.agent.state.get("debate_rounds") >= 3:
                event.agent.state.set(
                    "debate_action",
                    "Make final investment decision based on the analyses provided.",
                )
            else:
                event.agent.state.set(
                    "debate_action",
                    "Call Bull and Bear Researchers to debate on each other's analysis.",
                )

    def save_shared_document(self, event: AfterInvocationEvent):
        with open(self.shared_document_file, "r") as f:
            shared_document = json.load(f)

        message = event.agent.messages[-1]["content"][0]["text"]
        report_match = re.search(r"<think>(.*?)</think>(.*)", message, re.DOTALL)
        if report_match:
            report = report_match.group(2).strip()
        else:
            report = message

        event.agent.state.set(f"{event.agent.agent_id}_report", report)
        shared_document[f"{event.agent.agent_id}_report"] = report

        with open(self.shared_document_file, "w") as f:
            json.dump(shared_document, f)

    def _get_past_memories(self, shared_document):
        current_situation = f"""
Date: {shared_document.get('current_date')}
Ticker: {shared_document.get('ticker')}
Market Research Report: {shared_document.get('market_analyst_report')}
Latest World Affairs News: {shared_document.get('news_analyst_report')}
Company Fundamentals Report: {shared_document.get('fundamentals_analyst_report')}
Bull Researcher Analysis: {shared_document.get('bull_researcher_report')}
Bear Researcher Analysis: {shared_document.get('bear_researcher_report')}
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


class StoreMemoryHook(HookProvider):
    def __init__(self, memory_service):
        self.memory = memory_service

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterInvocationEvent, self.save_memory)

    def save_memory(self, event: AfterInvocationEvent):
        message = event.agent.messages[-1]["content"][0]["text"]
        report_match = re.search(r"<think>(.*?)</think>(.*)", message, re.DOTALL)
        if report_match:
            report = report_match.group(2).strip()
        else:
            report = message

        self.memory.add_memory(
            memory=f"Researcher Manager Decision for {event.agent.state.get('ticker')} on {event.agent.state.get('current_date')}: {report}",
            ticker=event.agent.state.get("ticker"),
        )
