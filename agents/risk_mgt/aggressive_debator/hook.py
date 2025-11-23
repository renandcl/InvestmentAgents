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
    def __init__(self, shared_document_file: str):
        self.shared_document_file = shared_document_file

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

        # Load reports
        event.agent.state.set(
            "market_research_report",
            shared_document.get(
                "market_research_report",
                shared_document.get(
                    "market_report", "No market research report available."
                ),
            ),
        )
        event.agent.state.set(
            "sentiment_report",
            shared_document.get(
                "sentiment_report",
                shared_document.get(
                    "social_sentiment_report", "No sentiment report available."
                ),
            ),
        )
        event.agent.state.set(
            "news_report",
            shared_document.get("news_report", "No news report available."),
        )
        event.agent.state.set(
            "fundamentals_report",
            shared_document.get(
                "fundamentals_report", "No fundamentals report available."
            ),
        )

        # Trader decision
        event.agent.state.set(
            "trader_decision",
            shared_document.get(
                "trader_investment_plan",
                shared_document.get(
                    "trader_decision",
                    shared_document.get(
                        "trader_report", "No trader decision available."
                    ),
                ),
            ),
        )

        # Risk debate state
        risk_debate = shared_document.get("risk_debate_state", {})
        event.agent.state.set(
            "history", risk_debate.get("history", "No debate history yet.")
        )
        event.agent.state.set(
            "conservative_report",
            shared_document.get(
                "conservative_analysis", "No conservative analysis yet."
            ),
        )
        event.agent.state.set(
            "neutral_report",
            shared_document.get("neutral_analysis", "No neutral analysis yet."),
        )

    def add_prompt_reports(self, event: BeforeModelInvocationEvent):
        system_prompt = event.agent.state.get("system_prompt")

        event.agent.system_prompt = system_prompt.format(
            ticker=event.agent.state.get("ticker", "UNKNOWN"),
            current_date=event.agent.state.get("current_date", "UNKNOWN"),
            market_research_report=event.agent.state.get("market_research_report"),
            sentiment_report=event.agent.state.get("sentiment_report"),
            news_report=event.agent.state.get("news_report"),
            fundamentals_report=event.agent.state.get("fundamentals_report"),
            trader_decision=event.agent.state.get("trader_decision"),
            history=event.agent.state.get("history"),
            conservative_report=event.agent.state.get("conservative_report"),
            neutral_report=event.agent.state.get("neutral_report"),
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

        event.agent.state.set(f"{event.agent.agent_id}_report", report)

        # Update risk_debate_state
        if "risk_debate_state" not in shared_document:
            shared_document["risk_debate_state"] = {}

        risk_debate_state = shared_document["risk_debate_state"]
        argument = f"Risky Analyst: {report}"

        risk_debate_state["history"] = (
            risk_debate_state.get("history", "") + "\n" + argument
        ).strip()
        risk_debate_state["risky_history"] = (
            risk_debate_state.get("risky_history", "") + "\n" + argument
        ).strip()
        risk_debate_state["latest_speaker"] = "Risky"
        risk_debate_state["current_risky_response"] = argument
        risk_debate_state["count"] = risk_debate_state.get("count", 0) + 1

        shared_document["risk_debate_state"] = risk_debate_state
        shared_document["aggressive_analysis"] = report

        with open(self.shared_document_file, "w") as f:
            json.dump(shared_document, f, indent=2)
