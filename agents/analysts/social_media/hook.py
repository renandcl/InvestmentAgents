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
    def __init__(self, shared_state_json_file: str):
        self.shared_state_file = shared_state_json_file

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_state)
        registry.add_callback(BeforeModelInvocationEvent, self.add_prompt_arguments)
        registry.add_callback(AfterInvocationEvent, self.save_shared_state)

    def get_shared_state(self, event: BeforeInvocationEvent):
        with open(self.shared_state_file, "r") as f:
            shared_state = json.load(f)

        event.agent.state.set("current_date", shared_state.get("current_date"))
        event.agent.state.set("ticker", shared_state.get("ticker"))
        event.agent.state.set("shared_state_file", self.shared_state_file)

    def add_prompt_arguments(self, event: BeforeModelInvocationEvent):
        event.agent.system_prompt = event.agent.system_prompt.format(
            ticker=event.agent.state.get("ticker"),
            date=event.agent.state.get("current_date"),
        )

    def save_shared_state(self, event: AfterInvocationEvent):
        with open(self.shared_state_file, "r") as f:
            shared_state = json.load(f)

        message = event.agent.messages[-1]["content"][0]["text"]
        # extract the report from the message using regex <think> ... </think>report
        report_match = re.search(r"<think>(.*?)</think>(.*)", message, re.DOTALL)
        if report_match:
            report = report_match.group(2).strip()
            event.agent.state.set(f"{event.agent.agent_id}_report", report)
            shared_state[f"{event.agent.agent_id}_report"] = report
        else:
            event.agent.state.set(f"{event.agent.agent_id}_report", message)
            shared_state[f"{event.agent.agent_id}_report"] = message

        with open(self.shared_state_file, "w") as f:
            json.dump(shared_state, f)