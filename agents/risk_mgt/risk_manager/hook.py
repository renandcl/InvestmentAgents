"""Select this agent's explicit lifecycle contract."""

from agents.hooks.lifecycle import AgentLifecycleHooks
from agents.hooks.specs import AGENT_SPECS


class SharedDocument(AgentLifecycleHooks):
    def __init__(self, shared_document_file: str, memory):
        super().__init__(AGENT_SPECS["risk_manager"], shared_document_file, memory)
