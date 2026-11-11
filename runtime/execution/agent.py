"""One serialized invocation boundary for tools, invoke_async and stream_async."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncIterator, Iterator
from contextlib import aclosing, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

from strands import Agent

from agents.debates.state import RoundContext
from agents.hooks.contracts import ContractError
from runtime.core.errors import RunContextMismatch, RunContextRequired
from runtime.execution.lifecycle import RunRuntime

if TYPE_CHECKING:
    from strands.types.agent import AgentInput

    from runtime.core.types import DebateHandle


def require_runtime(runtime: RunRuntime) -> RunRuntime:
    if not isinstance(runtime, RunRuntime):
        raise RunContextRequired("An explicit RunRuntime is required")
    runtime.assert_running()
    return runtime


type InvocationOwner = tuple[asyncio.AbstractEventLoop, asyncio.Task[Any] | None]


class InvocationWaiter(TypedDict):
    owner: InvocationOwner
    future: asyncio.Future[None]
    granted: bool


class InvocationGate:
    """FIFO gate across event loops; cancellation never strands an acquired slot."""

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self._owner: InvocationOwner | None = None
        self._waiters: deque[InvocationWaiter] = deque()

    async def __aenter__(self) -> InvocationGate:
        loop = asyncio.get_running_loop()
        owner = (loop, asyncio.current_task())
        with self._mutex:
            if self._owner == owner:
                raise ContractError("Recursive invocation of one agent is unsupported")
            if self._owner is None:
                self._owner = owner
                return self
            waiter: InvocationWaiter = {
                "owner": owner,
                "future": loop.create_future(),
                "granted": False,
            }
            self._waiters.append(waiter)
        try:
            await waiter["future"]
        except BaseException:
            with self._mutex:
                granted = waiter["granted"]
                if not granted:
                    self._waiters.remove(waiter)
            if granted:
                self._release()
            raise
        return self

    def _release(self) -> None:
        with self._mutex:
            self._owner = None
            if self._waiters:
                waiter = self._waiters.popleft()
                waiter["granted"] = True
                self._owner = waiter["owner"]

                def deliver() -> None:
                    if not waiter["future"].done():
                        waiter["future"].set_result(None)

                waiter["owner"][0].call_soon_threadsafe(deliver)

    async def __aexit__(self, *args: object) -> None:
        self._release()


@dataclass
class Invocation:
    invocation_id: str
    operation_id: str
    expected_revisions: dict[str, int]
    debate_handle: DebateHandle | None = None


class RunAgent(Agent):
    def __init__(self, *, runtime: RunRuntime, **kwargs: Any) -> None:
        self.runtime = require_runtime(runtime)
        self._invocation_gate = InvocationGate()
        self._active_invocation: Invocation | None = None
        super().__init__(**kwargs)

    def _prepare_invocation(
        self, invocation_state: dict[str, Any] | None
    ) -> tuple[Invocation, dict[str, Any]]:
        self.runtime.assert_running()
        state = dict(invocation_state or {})
        context = state.get("debate_context")
        if context is not None:
            if (
                not isinstance(context, RoundContext)
                or context.participant_id != self.agent_id
            ):
                raise RunContextMismatch("Invalid participant context")
            self.runtime.store.validate_round(
                handle=context.handle,
                participant_id=self.agent_id,
                round_number=context.round_number,
                phase=context.phase,
                snapshot=context.snapshot,
            )
        snapshot = self.runtime.store.read_snapshot()
        spec = self.lifecycle_hooks.spec
        invocation = Invocation(
            context.participant_invocation_id if context else uuid4().hex,
            uuid4().hex,
            {key: snapshot.revisions.get(key, 0) for key in spec.output_keys},
        )
        state["run_id"] = self.runtime.context.run_id
        state["invocation_id"] = invocation.invocation_id
        return invocation, state

    @contextmanager
    def _open_invocation(
        self, invocation: Invocation, *, fresh: bool
    ) -> Iterator[None]:
        task = self.runtime.enter_invocation()
        self._active_invocation = invocation
        failure: BaseException | None = None
        try:
            # Clearing is inside the same gate as session/model/hook activity.
            if fresh:
                self.messages.clear()
            yield
        except BaseException as error:
            failure = error
            raise
        finally:
            try:
                if invocation.debate_handle is not None:
                    self.runtime.store.end_debate(
                        debate_handle=invocation.debate_handle, outcome="aborted"
                    )
            except BaseException:
                if failure is None:
                    raise
            finally:
                self._active_invocation = None
                self.runtime.leave_invocation(task)

    def _check_result(self, invocation_id: str, result: Any) -> bool:
        if result.stop_reason in ("end_turn", "stop_sequence"):
            return True
        error = (
            asyncio.CancelledError()
            if result.stop_reason == "cancelled"
            else ContractError("Owned invocation did not complete")
        )
        self.runtime.record_invocation_failure(self.agent_id, invocation_id, error)
        return False

    async def stream_async(
        self,
        prompt: AgentInput = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        # Agent.invoke_async consumes self.stream_async, so only this outermost
        # boundary locks. Public @tool methods ultimately use the same path.
        invocation_id = uuid4().hex
        completed = False
        try:
            async with self._invocation_gate:
                invocation, state = self._prepare_invocation(invocation_state)
                invocation_id = invocation.invocation_id
                fresh = state.get("debate_context") is not None or bool(
                    self.lifecycle_hooks.spec.workflow
                )
                with self._open_invocation(invocation, fresh=fresh):
                    async with aclosing(
                        super().stream_async(prompt, invocation_state=state, **kwargs)
                    ) as stream:
                        async for event in stream:
                            if result := event.get("result"):
                                completed = self._check_result(invocation_id, result)
                            yield event
        except BaseException as error:
            if not (isinstance(error, GeneratorExit) and completed):
                self.runtime.record_invocation_failure(
                    self.agent_id, invocation_id, error
                )
            raise
