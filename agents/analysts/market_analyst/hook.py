"""Select this agent's explicit lifecycle contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.hooks.lifecycle import AgentLifecycleHooks
from agents.hooks.specs import AGENT_SPECS

if TYPE_CHECKING:
    from runtime.lifecycle import RunRuntime
    from runtime.types import MemoryService


class SharedDocument(AgentLifecycleHooks):
    def __init__(
        self, *, runtime: RunRuntime, memory: MemoryService | None = None
    ) -> None:
        super().__init__(AGENT_SPECS["market_analyst"], runtime=runtime, memory=memory)
