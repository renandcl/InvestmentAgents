"""Owned cleanup, registered before acquisition and bounded under cancellation."""

import asyncio
import inspect
import threading
from dataclasses import dataclass

from runtime.errors import ContractError, SafeError


@dataclass
class OwnedResource:
    close: object
    abort: object = None
    attempted: bool = False


async def call_cleanup(callback):
    if inspect.iscoroutinefunction(callback):
        return await callback()
    # MCP stop can block on a vendor thread. A daemon avoids indefinitely joining
    # a stuck default-executor thread when the application's event loop shuts down.
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def deliver(result, error):
        if not future.done():
            if error is None:
                future.set_result(result)
            else:
                future.set_exception(error)

    def run():
        result, error = None, None
        try:
            result = callback()
        except BaseException as exc:
            error = exc
        try:
            loop.call_soon_threadsafe(deliver, result, error)
        except RuntimeError:
            pass  # A timed-out cleanup may outlive the loop; never touch another run.

    threading.Thread(target=run, daemon=True, name="run-resource-cleanup").start()
    result = await future
    if inspect.isawaitable(result):
        return await result
    return result


class ResourceRegistry:
    def __init__(self, timeout=30.0):
        if not 0 < timeout <= 300:
            raise ContractError("Cleanup timeout must be bounded")
        self.timeout = timeout
        self._resources = []
        self._close_task = None
        self._closed = False
        self.errors = ()

    def register(self, close, *, abort=None):
        if self._closed or self._close_task is not None:
            raise ContractError("Cannot acquire resources during cleanup")
        resource = OwnedResource(close, abort)
        self._resources.append(resource)
        return resource

    async def _close(self):
        errors = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout
        resources = list(reversed(self._resources))
        for index, resource in enumerate(resources):
            if resource.attempted:
                continue
            resource.attempted = True
            # Reserve a share for each remaining callback, so one stuck resource
            # cannot prevent attempts to close the rest.
            budget = max(0.001, (deadline - loop.time()) / (len(resources) - index))
            task = asyncio.create_task(call_cleanup(resource.close))
            done, _ = await asyncio.wait({task}, timeout=budget)
            if not done:
                errors.append(SafeError("CleanupTimeout", "cleanup"))
                task.cancel()
                # Cancellation-resistant vendor coroutines are not awaited forever.
                task.add_done_callback(_consume)
                if resource.abort is not None:
                    abort_task = asyncio.create_task(call_cleanup(resource.abort))
                    abort_done, _ = await asyncio.wait(
                        {abort_task},
                        timeout=max(0.001, min(budget, deadline - loop.time())),
                    )
                    if not abort_done:
                        abort_task.cancel()
                        abort_task.add_done_callback(_consume)
                    else:
                        try:
                            abort_task.result()
                        except BaseException as error:
                            errors.append(SafeError.from_exception(error, "cleanup"))
            else:
                try:
                    task.result()
                except BaseException as error:
                    errors.append(SafeError.from_exception(error, "cleanup"))
        self.errors = tuple(errors)
        self._closed = True
        return self.errors

    async def close(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        cancelled = None
        while True:
            try:
                result = await asyncio.shield(self._close_task)
                break
            except asyncio.CancelledError as error:
                cancelled = error
        if cancelled is not None:
            raise cancelled
        return result


def _consume(task):
    if not task.cancelled():
        task.exception()
