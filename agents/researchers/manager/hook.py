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

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
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
            event.agent.state.set(f"{event.agent.agent_id}_report", report)
            shared_document[f"{event.agent.agent_id}_report"] = report
            # Also save as investment_plan for compatibility
            shared_document["investment_plan"] = report
            shared_document["judge_decision"] = report
        else:
            event.agent.state.set(f"{event.agent.agent_id}_report", message)
            shared_document[f"{event.agent.agent_id}_report"] = message
            shared_document["investment_plan"] = message
            shared_document["judge_decision"] = message

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
            for rec in records:
                memory_text = rec.get("memory") or rec.get("text")
                if not memory_text:
                    continue
                past_memory_str += memory_text + "\n\n"
            if past_memory_str:
                return past_memory_str

        return "No relevant past memories found."
