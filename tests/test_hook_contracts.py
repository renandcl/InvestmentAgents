"""Offline acceptance tests for explicit contracts and the registered lifecycle."""

import ast
import json
import runpy
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from isolation_helpers import fixture_replace, new_runtime, unit_agent, values
from strands.hooks import (
    AfterInvocationEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    HookRegistry,
)

from agents.hooks.contracts import ContractError
from agents.hooks.lifecycle import AgentLifecycleHooks
from agents.hooks.services import JsonReportStore, PromptRenderer, extract_report
from agents.hooks.specs import AGENT_SPECS

ROOT = Path(__file__).resolve().parents[1]


class State(dict):
    def set(self, key, value):
        self[key] = value


class HookContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.shared = Path(self.directory.name) / "shared.json"
        self.runtime = new_runtime(Path(self.directory.name))
        self.snapshot = {"ticker": "AAPL", "current_date": "2025-08-01"}
        self.write_snapshot()

    def write_snapshot(self):
        fixture_replace(self.runtime, self.snapshot)

    def make_agent(self, agent_id="trader"):
        spec = AGENT_SPECS[agent_id]
        memory = Mock(search_memories=Mock(return_value=[])) if spec.memory else None
        hook = AgentLifecycleHooks(spec, runtime=self.runtime, memory=memory)
        agent = unit_agent(self.runtime, agent_id)
        registry = HookRegistry()
        hook.register_hooks(registry)
        hook.get_shared_document(BeforeInvocationEvent(agent=agent))
        return hook, agent, registry

    def finish(self, agent, registry, text="Buy ten shares", stop_reason="end_turn"):
        result = SimpleNamespace(
            stop_reason=stop_reason,
            message={"role": "assistant", "content": [{"text": text}]},
        )
        registry.invoke_callbacks(AfterInvocationEvent(agent=agent, result=result))

    def test_every_agent_selects_one_matching_valid_contract(self):
        adapters = list((ROOT / "agents").rglob("hook.py"))
        self.assertEqual(len(adapters), 13)
        selected = set()
        outputs = set()
        for path in adapters:
            cls = runpy.run_path(str(path))["SharedDocument"]
            hook = cls(runtime=self.runtime, memory=Mock())
            spec = hook.spec
            with self.subTest(agent=spec.agent_id):
                self.assertIsInstance(hook, AgentLifecycleHooks)
                self.assertEqual(spec.prompt_path.parent, path.parent)
                self.assertFalse(outputs.intersection(spec.output_keys))
                outputs.update(spec.output_keys)
                selected.add(spec.agent_id)
        self.assertEqual(selected, set(AGENT_SPECS))

    def test_invalid_templates_and_bindings_fail_at_construction(self):
        original = AGENT_SPECS["market_analyst"]
        path = Path(self.directory.name) / "prompt.txt"
        for text in (
            "{unknown}",
            "{ticker.__class__}",
            "{ticker:{date}}",
            "{ticker",
            "{ticker!r}",
        ):
            with self.subTest(template=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ContractError, "market_analyst"):
                    PromptRenderer(replace(original, prompt_path=path))
        with self.assertRaisesRegex(ContractError, "undeclared source"):
            PromptRenderer(replace(original, prompt_bindings=(("ticker", "unknown"),)))

    def test_required_inputs_fail_before_memory_retrieval(self):
        for name in ("ticker", "current_date"):
            for value in (None, "", " ", 123):
                with self.subTest(field=name, value=value):
                    memory = Mock()
                    hook = AgentLifecycleHooks(
                        AGENT_SPECS["trader"], runtime=self.runtime, memory=memory
                    )
                    agent = unit_agent(self.runtime, "trader")
                    snapshot = self.runtime.store.read_snapshot()
                    broken = replace(
                        snapshot, values=dict(snapshot.values, **{name: value})
                    )
                    with (
                        patch.object(hook.store, "read_snapshot", return_value=broken),
                        self.assertRaisesRegex(ContractError, name),
                    ):
                        hook.get_shared_document(BeforeInvocationEvent(agent=agent))
                    memory.search_memories.assert_not_called()
                    self.assertEqual(agent.state, {})

    def test_wrong_agent_is_rejected(self):
        hook = AgentLifecycleHooks(AGENT_SPECS["market_analyst"], runtime=self.runtime)
        agent = SimpleNamespace(agent_id="news_analyst")
        with self.assertRaisesRegex(ContractError, "wrong agent"):
            hook.get_shared_document(BeforeInvocationEvent(agent=agent))

    def test_retrieved_memories_reach_prompt_without_reformatting_braces(self):
        for records in (
            [{"memory": 'Past trade {"shares": 2}'}],
            {"results": [{"text": 'Past trade {"shares": 2}'}]},
        ):
            with self.subTest(records=records):
                hook, agent, registry = self.make_agent()
                hook.memory.search_memories.return_value = records
                registry.invoke_callbacks(BeforeInvocationEvent(agent=agent))
                registry.invoke_callbacks(BeforeModelCallEvent(agent=agent))
                self.assertIn(
                    'Memory 1:\nPast trade {"shares": 2}', agent.system_prompt
                )
                hook.memory.search_memories.return_value = {"results": [{}]}
                registry.invoke_callbacks(BeforeInvocationEvent(agent=agent))
                registry.invoke_callbacks(BeforeModelCallEvent(agent=agent))
                self.assertNotIn("Past trade", agent.system_prompt)
                self.assertIn(hook.spec.memory.empty_text, agent.system_prompt)

    def test_rendering_does_not_advance_workflow(self):
        hook, agent, registry = self.make_agent("research_manager")
        agent.messages = [
            {"content": [{"toolResult": {"toolUseId": "one", "status": "success"}}]}
        ]
        before = deepcopy(agent.state)
        event = BeforeModelCallEvent(agent=agent)
        hook.add_prompt_arguments(event)
        hook.add_prompt_arguments(event)
        self.assertEqual(agent.state, before)
        registry.invoke_callbacks(event)
        self.assertEqual(agent.state["debate_rounds"], 0)
        registry.invoke_callbacks(event)
        self.assertEqual(agent.state["debate_rounds"], 0)

    def test_risk_peers_use_canonical_reports_and_clear_stale_inputs(self):
        peers = (
            "aggressive_risk_analyst",
            "conservative_risk_analyst",
            "neutral_risk_analyst",
        )
        self.snapshot.update(
            {f"{peer}_report": f"Argument from {peer}" for peer in peers}
        )
        self.write_snapshot()
        for peer in peers:
            with self.subTest(agent=peer):
                _, agent, registry = self.make_agent(peer)
                registry.invoke_callbacks(BeforeModelCallEvent(agent=agent))
                for other in set(peers) - {peer}:
                    self.assertIn(f"Argument from {other}", agent.system_prompt)
                fixture_replace(
                    self.runtime, {"ticker": "AAPL", "current_date": "2025-08-01"}
                )
                registry.invoke_callbacks(BeforeInvocationEvent(agent=agent))
                registry.invoke_callbacks(BeforeModelCallEvent(agent=agent))
                self.assertNotIn("Argument from", agent.system_prompt)
                self.write_snapshot()

    def test_absent_research_peer_is_cleared_on_reinvocation(self):
        self.snapshot["bear_researcher_report"] = "Old bear argument"
        self.write_snapshot()
        _, agent, registry = self.make_agent("bull_researcher")
        del self.snapshot["bear_researcher_report"]
        self.write_snapshot()
        registry.invoke_callbacks(BeforeInvocationEvent(agent=agent))
        registry.invoke_callbacks(BeforeModelCallEvent(agent=agent))
        self.assertNotIn("Old bear argument", agent.system_prompt)
        self.assertIn("Last bear argument: No report", agent.system_prompt)

    def test_finalize_extracts_once_and_commits_before_memory(self):
        hook, agent, registry = self.make_agent()

        def observe_commit(*, memory, ticker):
            snapshot = values(self.runtime.store)
            for key in hook.spec.output_keys:
                self.assertEqual(snapshot[key], 'Buy\n{"shares": 10}')
            self.assertEqual(ticker, "AAPL")
            self.assertIn('Buy\n{"shares": 10}', memory)
            self.assertNotIn("hidden", memory)

        hook.memory.add_memory.side_effect = observe_commit
        message = {
            "role": "assistant",
            "content": [
                {"reasoningContent": {"text": "hidden"}},
                {"text": "<think>hidden</think>Buy"},
                {"text": '<think>also hidden</think>{"shares": 10}'},
            ],
        }
        event = AfterInvocationEvent(
            agent=agent, result=SimpleNamespace(stop_reason="end_turn", message=message)
        )
        with patch(
            "agents.hooks.lifecycle.extract_report", wraps=extract_report
        ) as extract:
            registry.invoke_callbacks(event)
            registry.invoke_callbacks(event)
            extract.assert_called_once()
        hook.memory.add_memory.assert_called_once()

    def test_failed_results_do_not_reuse_old_history(self):
        for reason in (
            None,
            "cancelled",
            "interrupt",
            "max_tokens",
            "tool_use",
            "checkpoint",
        ):
            with self.subTest(stop_reason=reason):
                hook, agent, registry = self.make_agent()
                agent.messages = [
                    {"role": "assistant", "content": [{"text": "Old report"}]}
                ]
                if reason is None:
                    registry.invoke_callbacks(
                        AfterInvocationEvent(agent=agent, result=None)
                    )
                else:
                    self.finish(agent, registry, stop_reason=reason)
                self.assertEqual(values(self.runtime.store), self.snapshot)
                hook.memory.add_memory.assert_not_called()

    def test_receipt_replay_never_retries_external_memory(self):
        hook, agent, registry = self.make_agent()
        hook.memory.add_memory.side_effect = RuntimeError("Memory unavailable")
        with self.assertRaises(RuntimeError):
            self.finish(agent, registry, "Committed report")
        committed = self.runtime.store.read_snapshot()
        # Simulate a repeated callback with the original operation identity.
        agent.state.set("hook_finalized", False)
        self.finish(agent, registry, "Committed report")
        self.assertEqual(self.runtime.store.read_snapshot(), committed)
        hook.memory.add_memory.assert_called_once()

    def test_empty_and_invalid_reports_are_not_persisted(self):
        for text in ("", "<think>hidden</think>", "<think>unfinished"):
            with self.subTest(text=text):
                hook, agent, registry = self.make_agent()
                with self.assertRaises(ContractError):
                    self.finish(agent, registry, text)
                hook.memory.add_memory.assert_not_called()
                self.assertEqual(values(self.runtime.store), self.snapshot)

    def test_store_failure_prevents_memory_write(self):
        hook, agent, registry = self.make_agent()
        with patch.object(
            hook.store, "patch_reports", side_effect=OSError("unavailable")
        ):
            with self.assertRaises(OSError):
                self.finish(agent, registry)
        hook.memory.add_memory.assert_not_called()
        self.assertFalse(agent.state["hook_finalized"])

    def test_memory_failure_leaves_committed_report_and_propagates(self):
        hook, agent, registry = self.make_agent()
        hook.memory.add_memory.side_effect = RuntimeError("memory unavailable")
        with self.assertRaises(RuntimeError):
            self.finish(agent, registry)
        self.assertEqual(values(self.runtime.store)["trader_report"], "Buy ten shares")

    def test_replacement_failure_preserves_json_and_cleans_temporary_file(self):
        # Legacy adapter test remains separate from the isolated application path.
        self.shared.write_text(json.dumps(self.snapshot), encoding="utf-8")
        store = JsonReportStore(str(self.shared))
        with patch(
            "agents.hooks.services.os.replace", side_effect=OSError("unavailable")
        ):
            with self.assertRaises(OSError):
                store.patch({"trader_report": "new"})
        self.assertEqual(json.loads(self.shared.read_text()), self.snapshot)
        self.assertEqual(list(self.shared.parent.glob("*.json")), [self.shared])

    def test_both_constructor_paths_register_one_lifecycle_provider(self):
        for pattern in ("agent.py", "a2a_agent.py"):
            for path in (ROOT / "agents").rglob(pattern):
                with self.subTest(path=path.relative_to(ROOT)):
                    source = path.read_text(encoding="utf-8")
                    self.assertNotIn("StoreMemoryHook", source)
                    tree = ast.parse(source)
                    if path.name == "a2a_agent.py":
                        constructors = [
                            node
                            for node in ast.walk(tree)
                            if isinstance(node, ast.FunctionDef)
                            and node.name == "__init__"
                        ]
                        self.assertIsInstance(constructors[0].body[0], ast.Raise)
                        continue
                    hooks = [
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, ast.keyword) and node.arg == "hooks"
                    ]
                    self.assertEqual(len(hooks), 1)
                    expression = hooks[0].value
                    if isinstance(expression, ast.List):
                        self.assertEqual(len(expression.elts), 1)
                    else:
                        lists = [
                            node.value
                            for node in ast.walk(tree)
                            if isinstance(node, ast.Assign)
                            and any(
                                isinstance(target, ast.Attribute)
                                and target.attr == "hooks"
                                for target in node.targets
                            )
                        ]
                        self.assertEqual(len(lists), 1)
                        self.assertEqual(len(lists[0].elts), 1)


if __name__ == "__main__":
    unittest.main()
