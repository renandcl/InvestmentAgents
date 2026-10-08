"""One Strands adapter with explicit preparation and finalization ordering."""

from copy import deepcopy
from typing import Any

from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    HookProvider,
    HookRegistry,
)

from agents.debates.runner import DebateRunner
from agents.debates.state import RoundContext
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
        self.debate_runner: DebateRunner | None = None
        if spec.memory and memory is None:
            raise ContractError(f"{spec.agent_id}: memory service required by contract")

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(
            BeforeInvocationEvent,
            self.prepare_invocation if self.spec.workflow else self.get_shared_document,
        )
        registry.add_callback(BeforeModelCallEvent, self.prepare_model_call)
        registry.add_callback(AfterInvocationEvent, self.save_shared_document)

    async def prepare_invocation(self, event: BeforeInvocationEvent) -> None:
        if self.debate_runner is None:
            raise ContractError(
                f"{self.spec.agent_id}: distributed debate context is unsupported; "
                "configure local participants before invoking the manager"
            )
        self.get_shared_document(event, retrieve_memory=False)
        request = "\n".join(
            block["text"]
            for message in event.messages or []
            for block in message.get("content", [])
            if "text" in block
        )
        event.agent.messages.clear()
        result = await self.debate_runner.run(
            self.store.read(), request, self.spec.output_keys
        )
        snapshot = self.store.read()
        for field in self.spec.inputs:
            event.agent.state.set(
                field.name, field.resolve(snapshot, self.spec.agent_id)
            )
        event.agent.state.set("debate_rounds", len(result.completed))
        event.agent.state.set("debate_phase", result.phase)
        event.agent.state.set("debate_action", self.spec.workflow.final_action)
        self.retrieve_memories(snapshot, event)

    def get_shared_document(
        self, event: BeforeInvocationEvent, *, retrieve_memory: bool = True
    ) -> None:
        if event.agent.agent_id != self.spec.agent_id:
            raise ContractError(f"{self.spec.agent_id}: hook attached to wrong agent")
        context = getattr(event, "invocation_state", {}).get("debate_context")
        if context is not None and (
            not isinstance(context, RoundContext)
            or context.participant_id != self.spec.agent_id
            or self.spec.workflow is not None
        ):
            raise ContractError(f"{self.spec.agent_id}: invalid host debate context")
        snapshot = deepcopy(context.snapshot) if context else self.store.read()
        if policy := self.spec.workflow:
            for participant in policy.participants:
                snapshot.pop(participant.report_key, None)
            snapshot.pop(policy.history_key, None)
        # Resolve all required inputs before changing state or calling memory.
        values = {
            field.name: field.resolve(snapshot, self.spec.agent_id)
            for field in self.spec.inputs
        }
        state = event.agent.state
        state.set("system_prompt", self.system_prompt_template)
        state.set("shared_document_file", self.shared_document_file)
        state.set("hook_finalized", False)
        state.set("hook_staged", context is not None)
        for key in self.spec.output_keys:
            state.set(key, None)
        for name, value in values.items():
            state.set(name, value)
        if policy := self.spec.workflow:
            state.set("debate_rounds", 0)
            state.set("debate_phase", "opening")
            state.set(
                "debate_action", "Complete all participant rounds before synthesis."
            )
        if retrieve_memory:
            self.retrieve_memories(snapshot, event)

    def retrieve_memories(
        self, snapshot: dict[str, Any], event: BeforeInvocationEvent
    ) -> None:
        if policy := self.spec.memory:
            records = self.memory.search_memories(
                memory_query(policy, snapshot),
                ticker=event.agent.state.get("ticker"),
                n_matches=policy.n_matches,
            )
            event.agent.state.set(
                "past_memories", format_memories(records, policy.empty_text)
            )

    def prepare_model_call(self, event: BeforeModelCallEvent) -> None:
        self.add_prompt_arguments(event)

    def add_prompt_arguments(self, event: BeforeModelCallEvent) -> None:
        """Refresh declared inputs and render; never advance the workflow."""
        fields = [field for field in self.spec.inputs if field.refresh]
        if fields:
            context = getattr(event, "invocation_state", {}).get("debate_context")
            snapshot = context.snapshot if context else self.store.read()
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
        if event.agent.state.get("hook_staged"):
            return
        if self.spec.workflow and (
            event.agent.state.get("debate_rounds") != self.spec.workflow.max_rounds
            or event.agent.state.get("debate_phase") != "synthesis"
        ):
            raise ContractError(
                f"{self.spec.agent_id}: cannot synthesize an incomplete debate"
            )
        report = extract_report(result.message, self.spec.agent_id)
        changes = dict.fromkeys(self.spec.output_keys, report)
        self.store.patch(changes)
        for key, value in changes.items():
            event.agent.state.set(key, value)
        event.agent.state.set("hook_finalized", True)
        self.store_memory(
            report,
            {
                "ticker": event.agent.state.get("ticker"),
                "current_date": event.agent.state.get("current_date"),
            },
        )

    def store_memory(self, report: str, snapshot: dict[str, Any]) -> None:
        if policy := self.spec.memory:
            self.memory.add_memory(
                memory=(
                    f"{policy.store_label} for {snapshot.get('ticker')} "
                    f"on {snapshot.get('current_date')}: {report}"
                ),
                ticker=snapshot.get("ticker"),
            )
