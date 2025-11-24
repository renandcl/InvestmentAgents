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
    def __init__(self, shared_document_file: str):
        self.shared_document_file = shared_document_file

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

        # Load reports
        event.agent.state.set(
            "market_analyst_report",
            shared_document.get(
                "market_analyst_report", "No market analyst report available."
            ),
        )
        event.agent.state.set(
            "social_analyst_report",
            shared_document.get(
                "social_analyst_report", "No social analyst report available."
            ),
        )
        event.agent.state.set(
            "news_analyst_report",
            shared_document.get("news_analyst_report", "No news report available."),
        )
        event.agent.state.set(
            "fundamentals_analyst_report",
            shared_document.get(
                "fundamentals_analyst_report", "No fundamentals report available."
            ),
        )

        # Trader decision
        event.agent.state.set(
            "trader_investment_plan",
            shared_document.get(
                "trader_investment_plan", "No trader decision available."
            ),
        )

        # Risk debate state
        event.agent.state.set(
            "risk_debate_history",
            shared_document.get("risk_debate_history", "No debate history yet."),
        )
        event.agent.state.set(
            "aggressive_risk_analyst_report",
            shared_document.get("aggressive_analysis", "No aggressive analysis yet."),
        )
        event.agent.state.set(
            "conservative_risk_analyst_report",
            shared_document.get(
                "conservative_risk_analyst_report", "No conservative analysis yet."
            ),
        )

    def add_prompt_arguments(self, event: BeforeModelCallEvent):
        system_prompt = event.agent.state.get("system_prompt")

        event.agent.system_prompt = system_prompt.format(
            market_analyst_report=event.agent.state.get("market_analyst_report"),
            social_analyst_report=event.agent.state.get("social_analyst_report"),
            news_analyst_report=event.agent.state.get("news_analyst_report"),
            fundamentals_analyst_report=event.agent.state.get(
                "fundamentals_analyst_report"
            ),
            trader_investment_plan=event.agent.state.get("trader_investment_plan"),
            risk_debate_history=event.agent.state.get("risk_debate_history"),
            aggressive_risk_analyst_report=event.agent.state.get(
                "aggressive_risk_analyst_report"
            ),
            conservative_risk_analyst_report=event.agent.state.get(
                "conservative_risk_analyst_report"
            ),
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
