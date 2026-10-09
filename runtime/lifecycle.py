"""Run allocation and managed construction, invocation, cleanup and finalization."""

import asyncio
from uuid import uuid4

from agents.hooks.contracts import ContractError
from agents.hooks.specs import AGENT_SPECS
from runtime.artifacts import export_final, provenance, refresh_manifest
from runtime.context import allocate_context
from runtime.errors import RunExecutionError, RunNotWritable, SafeError
from runtime.resources import ResourceRegistry
from runtime.store import RunStore
from runtime.types import RunResult


class RunRuntime:
    def __init__(self, config, context, store):
        if store.context != context or (
            config.ticker,
            config.current_date,
            config.output_root,
        ) != (context.ticker, context.current_date, context.output_root):
            from runtime.errors import RunContextMismatch

            raise RunContextMismatch("Runtime dependencies belong to different runs")
        self.config = config
        self.context = context
        self.store = store
        self.resources = ResourceRegistry(config.cleanup_timeout)
        self._memories = {}
        self._executing = False
        self._accepting = True
        self._invocations = {}
        self._invocation_failure = None

    def record_invocation_failure(self, agent_id, invocation_id, error):
        # SDK tool executors may consume the exception. Keep its safe identity
        # after the completed child has left _invocations, without traceback data.
        failure = SafeError.from_exception(
            error, "invocation", agent_id=agent_id, invocation_id=invocation_id
        )
        if self._invocation_failure is None:
            self._invocation_failure = failure

    def assert_running(self):
        if not self._accepting or self.store.inspect()["status"] != "RUNNING":
            raise RunNotWritable("Runtime is not accepting invocations")

    def session_for(self, agent_id):
        self.assert_running()
        if agent_id not in AGENT_SPECS:
            raise ContractError("Unknown session owner")
        from strands.session.file_session_manager import FileSessionManager

        root = self.context.path("sessions", agent_id)
        root.mkdir(parents=True, exist_ok=True)
        return FileSessionManager(session_id=uuid4().hex, storage_dir=str(root))

    def memory_for(self, agent_id):
        self.assert_running()
        if agent_id not in AGENT_SPECS:
            raise ContractError("Unknown memory owner")
        if agent_id not in self._memories:
            from runtime.memory import create_memory

            self._memories[agent_id] = create_memory(self, agent_id)
        return self._memories[agent_id]

    def enter_invocation(self):
        self.assert_running()
        task = asyncio.current_task()
        self._invocations[task] = self._invocations.get(task, 0) + 1
        return task

    def leave_invocation(self, task):
        count = self._invocations.get(task, 0)
        if count > 1:
            self._invocations[task] = count - 1
        else:
            self._invocations.pop(task, None)

    async def _drain(self, *, cancel):
        tasks = set(self._invocations) - {asyncio.current_task()}
        if not tasks:
            return
        if cancel:
            for task in tasks:
                task.cancel()
        done, pending = await asyncio.wait(tasks, timeout=self.config.cleanup_timeout)
        if pending:
            for task in pending:
                task.cancel()
            from runtime.errors import CleanupTimeout

            raise CleanupTimeout("Owned invocations did not stop")
        for task in done:
            if not task.cancelled() and task.exception() is not None:
                raise task.exception()

    async def execute(self, agent_factory, message, required_report_key):
        if self._executing or self.store.inspect()["status"] != "CREATED":
            raise RunNotWritable("A run can execute only once")
        if required_report_key not in {
            key for spec in AGENT_SPECS.values() for key in spec.output_keys
        }:
            raise ContractError("Unknown root report")
        self._executing = True
        try:
            self.store.transition("CREATED", "RUNNING")
        except Exception as error:
            raise RunExecutionError(
                self.context, "UNKNOWN", SafeError.from_exception(error, "status")
            ) from None
        stage = "construction"
        error = None
        warnings = []
        try:
            refresh_manifest(self.store)
            agent = agent_factory(runtime=self)
            stage = "invocation"
            result = await agent.invoke_async(message)
            if getattr(result, "stop_reason", None) == "cancelled":
                raise asyncio.CancelledError()
            if getattr(result, "stop_reason", None) not in (
                "end_turn",
                "stop_sequence",
            ):
                raise ContractError("Root invocation did not complete")
            await self._drain(cancel=False)
            if self._invocation_failure is not None:
                if self._invocation_failure.category == "CancelledError":
                    raise asyncio.CancelledError()
                raise ContractError("An owned agent invocation failed")
            self._accepting = False
            stage = "cleanup"
            cleanup_errors = await self.resources.close()
            if cleanup_errors:
                raise ContractError("Owned resource cleanup failed")
            stage = "export"
            snapshot = self.store.read_snapshot()
            if not snapshot.values.get(required_report_key):
                raise ContractError("Required root report is absent")
            artifacts = export_final(self.context, snapshot)
            stage = "status"
            self.store.commit_success(
                artifacts=artifacts,
                required_report_key=required_report_key,
                expected_sequence=snapshot.sequence,
            )
        except BaseException as caught:
            error = caught
        if error is not None:
            self._accepting = False
            cleanup_errors = list(self.resources.errors)
            drain_task = asyncio.create_task(self._drain(cancel=True))
            while True:
                try:
                    await asyncio.shield(drain_task)
                    break
                except asyncio.CancelledError as cancelled:
                    error = cancelled
                    if drain_task.done():
                        break
                except BaseException as drain_error:
                    cleanup_errors.append(
                        SafeError.from_exception(drain_error, "cleanup")
                    )
                    break
            try:
                await self.resources.close()
            except asyncio.CancelledError as cancelled:
                error = cancelled
            cleanup_errors.extend(
                item for item in self.resources.errors if item not in cleanup_errors
            )
            safe_error = SafeError.from_exception(error, stage)
            if stage == "invocation" and self._invocation_failure is not None:
                safe_error = self._invocation_failure
            status = (
                "CANCELLED" if isinstance(error, asyncio.CancelledError) else "FAILED"
            )
            try:
                self.store.transition(
                    "RUNNING", status, error=safe_error, cleanup_errors=cleanup_errors
                )
            except BaseException:
                status = "UNKNOWN"
            try:
                refresh_manifest(self.store)
            except Exception:
                pass  # The persisted database outcome is authoritative.
            if isinstance(error, asyncio.CancelledError):
                error.run_id, error.run_root, error.status = (
                    self.context.run_id,
                    self.context.run_root,
                    status,
                )
                raise error
            raise RunExecutionError(self.context, status, safe_error) from None
        try:
            refresh_manifest(self.store)
        except Exception:
            warnings.append(
                "Manifest refresh failed; inspect run.sqlite3 for the committed outcome."
            )
        return RunResult(
            self.context.run_id,
            "SUCCEEDED",
            self.context.run_root,
            self.context.database_path,
            self.context.path("report.md"),
            self.context.path("shared_document.json"),
            tuple(warnings),
        )


def create_run(config):
    context = allocate_context(config)
    store = RunStore(context, timeout=config.busy_timeout)
    store.initialize(config, provenance())
    return RunRuntime(config, context, store)
