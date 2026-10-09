"""One serialized invocation boundary for tools, invoke_async and stream_async."""

import asyncio
import threading
from collections import deque
from contextlib import aclosing
from dataclasses import dataclass
from uuid import uuid4

from strands import Agent

from agents.debates.state import RoundContext
from agents.hooks.contracts import ContractError
from runtime.errors import RunContextMismatch, RunContextRequired
from runtime.lifecycle import RunRuntime


def require_runtime(runtime):
    if not isinstance(runtime, RunRuntime):
        raise RunContextRequired("An explicit RunRuntime is required")
    runtime.assert_running()
    return runtime


class InvocationGate:
    """FIFO gate across event loops; cancellation never strands an acquired slot."""

    def __init__(self):
        self._mutex = threading.Lock()
        self._owner = None
        self._waiters = deque()

    async def __aenter__(self):
        loop = asyncio.get_running_loop()
        owner = (loop, asyncio.current_task())
        with self._mutex:
            if self._owner == owner:
                raise ContractError("Recursive invocation of one agent is unsupported")
            if self._owner is None:
                self._owner = owner
                return self
            waiter = {"owner": owner, "future": loop.create_future(), "granted": False}
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

    def _release(self):
        with self._mutex:
            self._owner = None
            if self._waiters:
                waiter = self._waiters.popleft()
                waiter["granted"] = True
                self._owner = waiter["owner"]

                def deliver():
                    if not waiter["future"].done():
                        waiter["future"].set_result(None)

                waiter["owner"][0].call_soon_threadsafe(deliver)

    async def __aexit__(self, *args):
        self._release()


@dataclass
class Invocation:
    invocation_id: str
    operation_id: str
    expected_revisions: dict
    debate_handle: object = None


class RunAgent(Agent):
    def __init__(self, *, runtime, **kwargs):
        self.runtime = require_runtime(runtime)
        self._invocation_gate = InvocationGate()
        self._active_invocation = None
        self._last_invocation_id = None
        super().__init__(**kwargs)

    async def stream_async(self, prompt=None, *, invocation_state=None, **kwargs):
        # Agent.invoke_async consumes self.stream_async, so only this outermost
        # boundary locks. Public @tool methods ultimately use the same path.
        async with self._invocation_gate:
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
            self._active_invocation = invocation
            state["run_id"] = self.runtime.context.run_id
            state["invocation_id"] = invocation.invocation_id
            task = self.runtime.enter_invocation()
            failure = None
            completed = False
            try:
                # Clearing is inside the same gate as session/model/hook activity.
                if context is not None or spec.workflow:
                    self.messages.clear()
                async with aclosing(
                    super().stream_async(prompt, invocation_state=state, **kwargs)
                ) as stream:
                    async for event in stream:
                        if result := event.get("result"):
                            completed = result.stop_reason in (
                                "end_turn",
                                "stop_sequence",
                            )
                            if not completed:
                                error = (
                                    asyncio.CancelledError()
                                    if result.stop_reason == "cancelled"
                                    else ContractError(
                                        "Owned invocation did not complete"
                                    )
                                )
                                self.runtime.record_invocation_failure(
                                    self.agent_id, invocation.invocation_id, error
                                )
                        yield event
            except BaseException as error:
                failure = error
                if not (isinstance(error, GeneratorExit) and completed):
                    self.runtime.record_invocation_failure(
                        self.agent_id, invocation.invocation_id, error
                    )
                raise
            finally:
                try:
                    if invocation.debate_handle is not None:
                        self.runtime.store.end_debate(
                            debate_handle=invocation.debate_handle, outcome="aborted"
                        )
                except BaseException as error:
                    self.runtime.record_invocation_failure(
                        self.agent_id, invocation.invocation_id, error
                    )
                    if failure is None:
                        raise
                finally:
                    self._last_invocation_id = invocation.invocation_id
                    self._active_invocation = None
                    self.runtime.leave_invocation(task)
