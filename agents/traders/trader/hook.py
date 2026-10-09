"""Select this agent's explicit lifecycle contract."""

from agents.hooks.lifecycle import AgentLifecycleHooks
from agents.hooks.specs import AGENT_SPECS


class SharedDocument(AgentLifecycleHooks):
    def __init__(self, *, runtime, memory=None):
        super().__init__(AGENT_SPECS["trader"], runtime=runtime, memory=memory)
