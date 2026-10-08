"""Participant quorum and real Strands lifecycle checks without external services."""

import asyncio
import importlib
import json
import logging
import tempfile
import unittest
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from strands import Agent
from strands.models.model import Model

from agents.debates.runner import DebateRunner
from agents.debates.state import DebateState
from agents.hooks.contracts import ContractError
from agents.hooks.lifecycle import AgentLifecycleHooks
from agents.hooks.services import JsonReportStore
from agents.hooks.specs import AGENT_SPECS


class DebateStateTests(unittest.TestCase):
    def setUp(self):
        self.policy = AGENT_SPECS["research_manager"].workflow
        self.state = DebateState(self.policy, "test-debate")

    def test_quorum_is_required_for_each_round(self):
        self.state.accept(1, "bull_researcher", "one", "Bull opening")
        with self.assertRaises(ContractError):
            self.state.finish_round()
        self.assertEqual(self.state.round_number, 1)
        self.state.accept(1, "bear_researcher", "two", "Bear opening")
        self.state.finish_round()
        self.assertEqual(self.state.phase, "rebuttal")
        self.assertEqual(self.state.round_number, 2)

    def test_duplicate_is_idempotent_even_after_round_completion(self):
        self.state.accept(1, "bull_researcher", "one", "Bull opening")
        self.assertFalse(self.state.accept(1, "bull_researcher", "one", "Bull opening"))
        self.state.accept(1, "bear_researcher", "two", "Bear opening")
        self.state.finish_round()
        self.assertFalse(self.state.accept(1, "bull_researcher", "one", "Bull opening"))
        self.assertEqual(self.state.pending, {})
        self.assertEqual(len(self.state.completed), 1)

    def test_conflicting_unknown_and_wrong_round_contributions_fail(self):
        self.state.accept(1, "bull_researcher", "one", "Bull opening")
        for args in (
            (1, "bull_researcher", "one", "Changed"),
            (1, "bull_researcher", "new", "Extra bull"),
            (1, "trader", "new", "Unrelated"),
            (2, "bear_researcher", "new", "Too early"),
            (1, "bear_researcher", "new", ""),
        ):
            with self.subTest(args=args), self.assertRaises(ContractError):
                self.state.accept(*args)
        self.assertEqual(set(self.state.pending), {"bull_researcher"})

    def test_synthesis_only_after_all_three_phases(self):
        for number, phase in enumerate(self.policy.phases, 1):
            self.assertEqual(self.state.phase, phase)
            for participant in self.policy.participants:
                self.state.accept(
                    number,
                    participant.agent_id,
                    f"{number}-{participant.agent_id}",
                    phase,
                )
            self.state.finish_round()
        self.assertTrue(self.state.finished)
        self.assertEqual(self.state.phase, "synthesis")
        with self.assertRaises(ContractError):
            self.state.accept(4, "bull_researcher", "four", "Extra")


class ScriptedModel(Model):
    """Emit the SDK's normal stream format and inspect actual invocation context."""

    def __init__(self, agent_id, calls, store, failure=None):
        self.agent_id = agent_id
        self.calls = calls
        self.store = store
        self.failure = failure

    def update_config(self, **model_config):
        pass

    def get_config(self):
        return {"model_id": "offline-script"}

    async def structured_output(self, *args, **kwargs):
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        context = kwargs.get("invocation_state", {}).get("debate_context")
        round_number = context.round_number if context else None
        self.calls.append(
            {
                "agent_id": self.agent_id,
                "round": round_number,
                "snapshot": deepcopy(context.snapshot) if context else None,
                "published": self.store.read(),
                "prompt": system_prompt,
                "messages": deepcopy(messages),
                "tool_specs": tool_specs,
            }
        )
        if self.failure and self.failure[0] == round_number:
            action = self.failure[1]
            if action == "cancel":
                raise asyncio.CancelledError
            if action == "error":
                raise RuntimeError("Participant failed")
            text = "<think>no report</think>"
        else:
            text = (
                f"{self.agent_id} {context.phase}"
                if context
                else "BUY: complete debate evaluated"
            )
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": text}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 0},
            }
        }


class DebateIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.shared = Path(self.directory.name) / "shared.json"
        self.initial = {
            "ticker": "AAPL",
            "current_date": "2025-08-01",
            "market_analyst_report": 'Market {"price": 10}',
            "fundamentals_analyst_report": "Fundamentals",
            "news_analyst_report": "News",
            "trader_investment_plan": "Trade plan",
        }
        self.shared.write_text(json.dumps(self.initial), encoding="utf-8")
        self.calls = []
        strands_logger = logging.getLogger("strands")
        previous = strands_logger.level
        strands_logger.setLevel(logging.CRITICAL)
        self.addCleanup(strands_logger.setLevel, previous)

    def build(self, manager_id="research_manager", failure=None, reverse=False):
        spec = AGENT_SPECS[manager_id]
        if reverse:
            spec = replace(
                spec,
                workflow=replace(
                    spec.workflow,
                    participants=tuple(reversed(spec.workflow.participants)),
                ),
            )
        hook = AgentLifecycleHooks(
            spec, str(self.shared), Mock(search_memories=Mock(return_value=[]))
        )
        participants = {}
        for number, participant in enumerate(spec.workflow.participants):
            child_spec = AGENT_SPECS[participant.agent_id]
            memory = (
                Mock(search_memories=Mock(return_value=[]))
                if child_spec.memory
                else None
            )
            child_hook = AgentLifecycleHooks(child_spec, str(self.shared), memory)
            model = ScriptedModel(
                participant.agent_id,
                self.calls,
                hook.store,
                failure if number == 1 else None,
            )
            child = Agent(
                agent_id=participant.agent_id,
                model=model,
                hooks=[child_hook],
                callback_handler=None,
            )
            child.lifecycle_hooks = child_hook
            participants[participant.agent_id] = child
        hook.debate_runner = DebateRunner(spec.workflow, participants, hook.store)
        manager = Agent(
            agent_id=manager_id,
            model=ScriptedModel(manager_id, self.calls, hook.store),
            hooks=[hook],
            tools=[],
            callback_handler=None,
        )
        return manager, hook, participants

    async def test_research_and_risk_complete_all_participants_before_synthesis(self):
        for manager_id, count in (("research_manager", 2), ("risk_manager", 3)):
            with self.subTest(manager=manager_id):
                self.calls.clear()
                manager, hook, participants = self.build(manager_id)
                result = await manager.invoke_async("Evaluate the ticker")
                self.assertEqual(result.stop_reason, "end_turn")
                self.assertEqual(len(self.calls), count * 3 + 1)
                self.assertEqual(
                    [call["round"] for call in self.calls[:-1]],
                    [n for n in (1, 2, 3) for _ in range(count)],
                )
                for round_number in (1, 2, 3):
                    calls = [
                        call for call in self.calls if call["round"] == round_number
                    ]
                    self.assertEqual(
                        {call["agent_id"] for call in calls}, set(participants)
                    )
                    self.assertTrue(
                        all(call["snapshot"] == calls[0]["snapshot"] for call in calls)
                    )
                    self.assertTrue(
                        all(
                            call["published"] == calls[0]["published"] for call in calls
                        )
                    )
                    for call in calls:
                        # Fresh messages make the frozen snapshot the complete peer context.
                        self.assertEqual(len(call["messages"]), 1)
                        if round_number > 1:
                            self.assertIn(
                                f"Round {round_number - 1}",
                                call["snapshot"][hook.spec.workflow.history_key],
                            )
                        self.assertIn(
                            call["snapshot"][hook.spec.workflow.history_key],
                            call["prompt"],
                        )
                synthesis = self.calls[-1]
                self.assertFalse(synthesis["tool_specs"])
                self.assertIn("Debate Phase: synthesis", synthesis["prompt"])
                self.assertIn("Round 3 (clarification)", synthesis["prompt"])
                snapshot = hook.store.read()
                self.assertTrue(
                    all(
                        snapshot[key] == str(result).strip()
                        for key in hook.spec.output_keys
                    )
                )
                for participant in participants.values():
                    if participant.lifecycle_hooks.memory:
                        self.assertEqual(
                            participant.lifecycle_hooks.memory.add_memory.call_count, 3
                        )
                hook.memory.add_memory.assert_called_once()

    async def test_reversing_execution_order_preserves_snapshots_and_history(self):
        manager, hook, _ = self.build()
        await manager.invoke_async("Evaluate")
        forward = {(c["round"], c["agent_id"]): c["snapshot"] for c in self.calls[:-1]}
        transcript = hook.store.read()[hook.spec.workflow.history_key]
        self.shared.write_text(json.dumps(self.initial), encoding="utf-8")
        self.calls.clear()
        manager, hook, _ = self.build(reverse=True)
        await manager.invoke_async("Evaluate")
        reverse = {(c["round"], c["agent_id"]): c["snapshot"] for c in self.calls[:-1]}
        self.assertEqual(forward, reverse)
        self.assertEqual(transcript, hook.store.read()[hook.spec.workflow.history_key])

    async def test_failures_do_not_publish_partial_round_or_synthesize(self):
        for action in ("error", "empty", "cancel"):
            with self.subTest(action=action):
                self.shared.write_text(json.dumps(self.initial), encoding="utf-8")
                self.calls.clear()
                manager, hook, participants = self.build(failure=(1, action))
                exception = (
                    asyncio.CancelledError
                    if action == "cancel"
                    else (RuntimeError, ContractError)
                )
                with self.assertRaises(exception):
                    await manager.invoke_async("Evaluate")
                snapshot = hook.store.read()
                self.assertEqual(snapshot, self.initial)
                self.assertFalse(
                    any(call["agent_id"] == "research_manager" for call in self.calls)
                )
                hook.memory.add_memory.assert_not_called()
                for participant in participants.values():
                    participant.lifecycle_hooks.memory.add_memory.assert_not_called()

    async def test_failure_after_first_round_retains_only_completed_history(self):
        manager, hook, participants = self.build(failure=(2, "error"))
        with self.assertRaises(RuntimeError):
            await manager.invoke_async("Evaluate")
        snapshot = hook.store.read()
        self.assertIn("Round 1 (opening)", snapshot[hook.spec.workflow.history_key])
        self.assertNotIn("Round 2", snapshot[hook.spec.workflow.history_key])
        self.assertNotIn("research_manager_report", snapshot)
        for participant in participants.values():
            self.assertEqual(
                participant.lifecycle_hooks.memory.add_memory.call_count, 1
            )

    async def test_json_failure_prevents_round_memory_and_synthesis(self):
        manager, hook, participants = self.build()
        original = hook.store.patch

        def commit(changes, **kwargs):
            if changes:
                raise OSError("Cannot publish round")
            return original(changes, **kwargs)

        with (
            patch.object(hook.store, "patch", side_effect=commit),
            self.assertRaises(OSError),
        ):
            await manager.invoke_async("Evaluate")
        self.assertEqual(hook.store.read(), self.initial)
        hook.memory.add_memory.assert_not_called()
        for participant in participants.values():
            participant.lifecycle_hooks.memory.add_memory.assert_not_called()

    async def test_new_invocation_clears_stale_peer_history_and_final_alias(self):
        manager, hook, participants = self.build("risk_manager")
        await manager.invoke_async("Evaluate")
        self.calls.clear()
        await manager.invoke_async("Evaluate again")
        for call in self.calls[:3]:
            self.assertNotIn("final_trade_decision", call["published"])
            self.assertEqual(
                call["snapshot"]["risk_debate_history"], "No debate history yet."
            )
            for participant in hook.spec.workflow.participants:
                self.assertNotIn(participant.report_key, call["snapshot"])

    async def test_stream_api_also_runs_the_debate(self):
        manager, hook, _ = self.build()
        events = [event async for event in manager.stream_async("Evaluate")]
        self.assertTrue(any("result" in event for event in events))
        self.assertEqual(len(self.calls), 7)
        self.assertIn("research_manager_report", hook.store.read())

    async def test_public_manager_tools_bind_and_run_the_scheduler(self):
        for manager_id, module_name, class_name, tool_name in (
            (
                "research_manager",
                "agents.researchers.manager.agent",
                "ResearchManager",
                "get_research_manager_investment_plan",
            ),
            (
                "risk_manager",
                "agents.risk_mgt.risk_manager.agent",
                "RiskManager",
                "get_risk_manager_evaluation_and_decision",
            ),
        ):
            with self.subTest(manager=manager_id), ExitStack() as stack:
                self.calls.clear()
                specs = [AGENT_SPECS[manager_id]] + [
                    AGENT_SPECS[p.agent_id]
                    for p in AGENT_SPECS[manager_id].workflow.participants
                ]
                for spec in specs:
                    module_path = (
                        ".".join(
                            spec.prompt_path.parent.relative_to(
                                Path(__file__).resolve().parents[1]
                            ).parts
                        )
                        + ".agent"
                    )
                    module = importlib.import_module(module_path)
                    original_hook = module.SharedDocument

                    def make_hook(*args, _original=original_hook, **kwargs):
                        memory = args[1] if len(args) > 1 else kwargs.get("memory")
                        return (
                            _original(str(self.shared), memory)
                            if memory is not None
                            else _original(str(self.shared))
                        )

                    stack.enter_context(
                        patch.object(module, "SharedDocument", side_effect=make_hook)
                    )
                    stack.enter_context(
                        patch.object(module, "FileSessionManager", return_value=None)
                    )
                    stack.enter_context(
                        patch.object(
                            module,
                            "OpenAIModel",
                            return_value=ScriptedModel(
                                spec.agent_id,
                                self.calls,
                                JsonReportStore(str(self.shared)),
                            ),
                        )
                    )
                    if hasattr(module, "MemoryService"):
                        stack.enter_context(
                            patch.object(
                                module,
                                "MemoryService",
                                side_effect=lambda **_: Mock(
                                    search_memories=Mock(return_value=[])
                                ),
                            )
                        )
                manager_module = importlib.import_module(module_name)
                logging.getLogger("strands").setLevel(logging.CRITICAL)
                manager = getattr(manager_module, class_name)()
                manager.callback_handler = lambda **_: None
                for (
                    child
                ) in manager.lifecycle_hooks.debate_runner.participants.values():
                    child.callback_handler = lambda **_: None
                result = await getattr(manager, tool_name)("Evaluate")
                self.assertEqual(result.stop_reason, "end_turn")
                self.assertEqual(
                    len(self.calls), len(specs[0].workflow.participants) * 3 + 1
                )

    async def test_participant_memory_is_written_only_after_full_round_publication(
        self,
    ):
        manager, hook, participants = self.build()
        observations = []
        for participant in participants.values():

            def observe(*, memory, ticker):
                snapshot = hook.store.read()
                phase = memory.rsplit(" ", 1)[-1]
                for peer in hook.spec.workflow.participants:
                    self.assertEqual(
                        snapshot[peer.report_key], f"{peer.agent_id} {phase}"
                    )
                observations.append(snapshot[hook.spec.workflow.history_key])

            participant.lifecycle_hooks.memory.add_memory.side_effect = observe
        await manager.invoke_async("Evaluate")
        self.assertEqual(len(observations), 6)

    async def test_manager_memory_failure_cannot_leave_stale_final_report(self):
        manager, hook, _ = self.build()
        await manager.invoke_async("Evaluate")
        self.calls.clear()
        hook.memory.search_memories.side_effect = RuntimeError("Memory unavailable")
        with self.assertRaises(RuntimeError):
            await manager.invoke_async("Evaluate again")
        self.assertNotIn("research_manager_report", hook.store.read())
        self.assertFalse(
            any(call["agent_id"] == "research_manager" for call in self.calls)
        )

    def test_distributed_variants_reject_before_service_construction(self):
        for module_name, class_name in (
            ("agents.researchers.manager.a2a_agent", "ResearchManager"),
            ("agents.risk_mgt.risk_manager.a2a_agent", "RiskManager"),
        ):
            module = importlib.import_module(module_name)
            with (
                patch.object(module, "OpenAIModel") as model,
                patch.object(module, "MemoryService") as memory,
            ):
                with self.assertRaisesRegex(
                    ContractError, "HTTP round-context propagation"
                ):
                    getattr(module, class_name)()
                model.assert_not_called()
                memory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
