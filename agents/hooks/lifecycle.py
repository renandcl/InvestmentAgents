"""One Strands adapter with explicit preparation and finalization ordering."""

from copy import deepcopy
from typing import Any

from strands.hooks import (
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    HookProvider,
    HookRegistry,
)

from agents.hooks.contracts import AgentSpec, ContractError
from agents.hooks.services import (
    JsonReportStore,
    PromptRenderer,
    extract_report,
    format_memories,
    memory_query,
)


class AgentLifecycleHooks(HookProvider):
    def __init__(self, spec: AgentSpec, shared_document_file: str, memory: Any = None):
        self.spec = spec
        self.shared_document_file = shared_document_file
        self.renderer = PromptRenderer(spec)
        self.system_prompt_template = self.renderer.template
        self.store = JsonReportStore(shared_document_file)
        self.memory = memory
        if spec.memory and memory is None:
            raise ContractError(f"{spec.agent_id}: memory service required by contract")

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.get_shared_document)
        registry.add_callback(BeforeModelCallEvent, self.prepare_model_call)
        registry.add_callback(AfterInvocationEvent, self.save_shared_document)
        if self.spec.workflow and self.spec.workflow.track_history:
            registry.add_callback(AfterModelCallEvent, self.update_history)
            registry.add_callback(AfterToolCallEvent, self.update_history)

    def get_shared_document(self, event: BeforeInvocationEvent) -> None:
        if event.agent.agent_id != self.spec.agent_id:
            raise ContractError(f"{self.spec.agent_id}: hook attached to wrong agent")
        snapshot = self.store.read()
        # Resolve all required inputs before changing state or calling memory.
        values = {
            field.name: field.resolve(snapshot, self.spec.agent_id)
            for field in self.spec.inputs
        }
        state = event.agent.state
        state.set("system_prompt", self.system_prompt_template)
        state.set("shared_document_file", self.shared_document_file)
        state.set("hook_finalized", False)
        for name, value in values.items():
            state.set(name, value)
        if policy := self.spec.workflow:
            state.set("debate_rounds", 0)
            state.set("processed_debate_results", [])
            state.set("debate_action", policy.opening_action)
            if policy.track_history:
                state.set("risk_debate_history", None)
        if policy := self.spec.memory:
            records = self.memory.search_memories(
                memory_query(policy, snapshot),
                ticker=state.get("ticker"),
                n_matches=policy.n_matches,
            )
            state.set("past_memories", format_memories(records, policy.empty_text))

    def prepare_model_call(self, event: BeforeModelCallEvent) -> None:
        if policy := self.spec.workflow:
            state = event.agent.state
            last = event.agent.messages[-1] if event.agent.messages else {}
            rounds, processed, action = policy.advance(
                state.get("debate_rounds"), state.get("processed_debate_results"), last
            )
            state.set("debate_rounds", rounds)
            state.set("processed_debate_results", processed)
            if action is not None:
                state.set("debate_action", action)
        self.add_prompt_arguments(event)

    def add_prompt_arguments(self, event: BeforeModelCallEvent) -> None:
        """Refresh declared inputs and render; never advance the workflow."""
        fields = [field for field in self.spec.inputs if field.refresh]
        if fields:
            snapshot = self.store.read()
            for field in fields:
                event.agent.state.set(
                    field.name, field.resolve(snapshot, self.spec.agent_id)
                )
        context = {
            name: event.agent.state.get(source)
            for name, source in self.spec.prompt_bindings
        }
        event.agent.system_prompt = self.renderer.render(context)

    def save_shared_document(self, event: AfterInvocationEvent) -> None:
        # AfterInvocation fires on errors too. Never infer success from history.
        result = event.result
        if result is None or result.stop_reason not in ("end_turn", "stop_sequence"):
            return
        if event.agent.state.get("hook_finalized"):
            return
        report = extract_report(result.message, self.spec.agent_id)
        changes = dict.fromkeys(self.spec.output_keys, report)
        self.store.patch(changes)
        for key, value in changes.items():
            event.agent.state.set(key, value)
        event.agent.state.set("hook_finalized", True)
        if policy := self.spec.memory:
            self.memory.add_memory(
                memory=(
                    f"{policy.store_label} for {event.agent.state.get('ticker')} "
                    f"on {event.agent.state.get('current_date')}: {report}"
                ),
                ticker=event.agent.state.get("ticker"),
            )

    def update_history(self, event: AfterModelCallEvent | AfterToolCallEvent) -> None:
        event.agent.state.set("risk_debate_history", deepcopy(event.agent.messages))
