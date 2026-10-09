"""Test-only fixtures; production report ownership is exercised through RunStore."""

from types import SimpleNamespace
from uuid import uuid4

from agents.hooks.specs import AGENT_SPECS
from runtime.agent import Invocation
from runtime.context import RunConfig, allocate_context
from runtime.lifecycle import RunRuntime
from runtime.store import RunStore
from runtime.types import Contribution


class State(dict):
    def set(self, key, value):
        self[key] = value


def new_runtime(root, ticker="AAPL", current_date="2025-08-01"):
    config = RunConfig(ticker, current_date, output_root=root)
    context = allocate_context(config)
    store = RunStore(context)
    store.initialize(
        config,
        {
            "code_revision": None,
            "dirty": None,
            "lockfile_hash": None,
            "prompt_hashes": {},
        },
    )
    store.transition("CREATED", "RUNNING")
    return RunRuntime(config, context, store)


def fixture_replace(runtime, values):
    """Load analyst inputs directly for unit tests, never an application fallback."""
    assert values.get("ticker", runtime.context.ticker) == runtime.context.ticker
    assert (
        values.get("current_date", runtime.context.current_date)
        == runtime.context.current_date
    )
    with runtime.store._transaction(write=True) as db:
        db.execute("DELETE FROM state")
        db.execute("DELETE FROM debates")
        db.execute("DELETE FROM rounds")
        db.execute("DELETE FROM operations")
        for key, value in values.items():
            if key not in {"ticker", "current_date"}:
                runtime.store._write(db, key, value, "fixture", "fixture", uuid4().hex)
        runtime.store._event(db, "fixture", {})


def values(store):
    return {
        key: value
        for key, value in store.read_snapshot().values.items()
        if key not in {"run_id", "schema_version", "created_at", "status"}
    }


def unit_agent(runtime, agent_id):
    spec = AGENT_SPECS[agent_id]
    snapshot = runtime.store.read_snapshot()
    return SimpleNamespace(
        agent_id=agent_id,
        runtime=runtime,
        state=State(),
        messages=[],
        system_prompt="",
        _active_invocation=Invocation(
            uuid4().hex,
            uuid4().hex,
            {key: snapshot.revisions.get(key, 0) for key in spec.output_keys},
        ),
    )


def complete_manager_fixture(hook, agent):
    invocation = agent._active_invocation
    start = hook.store.begin_debate(
        manager_id=hook.spec.agent_id,
        manager_invocation_id=invocation.invocation_id,
        operation_id=uuid4().hex,
    )
    invocation.debate_handle = start.handle
    invocation.expected_revisions = {
        key: start.snapshot.revisions[key] for key in hook.spec.output_keys
    }
    policy = hook.spec.workflow
    for number in range(1, 4):
        snapshot = hook.store.read_snapshot()
        keys = [p.report_key for p in policy.participants] + [policy.history_key]
        hook.store.commit_round(
            debate_handle=start.handle,
            operation_id=uuid4().hex,
            round_number=number,
            contributions={
                p.agent_id: Contribution(
                    f"{p.agent_id} round {number}", uuid4().hex, uuid4().hex
                )
                for p in policy.participants
            },
            expected_revisions={key: snapshot.revisions[key] for key in keys},
        )
    agent.state.set("debate_rounds", 3)
    agent.state.set("debate_phase", "synthesis")
