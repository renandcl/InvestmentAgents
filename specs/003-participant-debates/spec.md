# 003 - Participant-aware debates

Status: Implemented and validated offline. Prepared: 2026-10-08.

## Problem

The managers count successful tool-result turns rather than complete rounds.
An LLM can omit a participant, stop early, or give later participants access to
earlier contributions from the same round. Risk history is local to the manager.

## Requirements

1. Python schedules three phases: opening, rebuttal, clarification, then manager
   synthesis. Each research round requires bull and bear. Each risk round
   requires aggressive, conservative and neutral. No participant can be skipped.
2. All participants in a round read copies of the same snapshot containing only
   prior completed rounds. Opening starts with no stale peer reports/history.
   Participant invocation context is supplied by host code, never a model tool.
3. A round completes only after one nonempty successful assistant contribution
   from every configured participant. Duplicate operations cannot advance a
   round; conflicting duplicates and wrong-round/unknown-participant results fail.
4. Stage contributions in memory. Publish all reports and the full accepted
   history together using one JSON replacement after the quorum is complete.
   Only then store participant memories. Failures/cancellation publish no partial
   round and prevent manager synthesis/final report. Previously completed rounds
   remain available for diagnosis. Failed attempts are not automatically retried.
   If memory storage fails after publication, the complete round remains committed
   and synthesis fails; already written external memories are not rolled back.
5. Clear prior outputs/history for this debate at invocation start, including old
   manager output aliases. Starting a new invocation starts a fresh debate;
   resumability and exactly-once external memory are outside this specification.
6. The manager receives all completed contributions and makes one synthesis
   invocation without participant tools. Prompts describe reasoning and phase
   context, with round count/phase/history generated from the Python policy.
   Manager memory retrieval happens after the rounds complete. Conversation
   messages are cleared at each participant invocation and new manager debate;
   the explicit accepted history supplies the context for prior arguments.
7. Keep public manager tools, agent IDs, ports and report aliases. Run the debate
   from the manager's invocation hook so invoke_async, stream_async and its A2A
   server all use the same scheduler. Distributed a2a_agent.py manager variants
   reject execution explicitly before memory/model/network side effects until
   host round-context propagation over HTTP is implemented. In-process managers
   served through A2A continue using local participants.

## Design

Replace ToolResultTurnPolicy with frozen DebatePolicy and ParticipantSpec.
agents/debates/state.py owns round/quorum/duplicate rules independently of SDK
events. agents/debates/runner.py schedules local participants sequentially for
predictable resource use, with the same snapshot semantics as parallel execution.
RoundContext carries a host-generated debate ID, round, phase, participant and
snapshot. Shared hooks load staged contexts and defer participant publication.

The manager hook calls the runner during BeforeInvocationEvent, then renders the
completed state. BeforeModelCallEvent only refreshes/render context; messages,
tool batches and model retries never advance rounds. Both histories are persisted
as readable strings in research_debate_history and risk_debate_history.

This changes debate behavior independently of spec 002's preserved baseline.
Spec 001 remains proposed: the shared JSON adapter does not isolate concurrent
debates/runs across processes. Top-level investment phase sequencing is unchanged.

## Acceptance

- Research schedules six contributions; risk schedules nine, followed by one
  synthesis. Every phase has all participants exactly once.
- Reversing participant order produces identical input snapshots and accepted
  history ordering. Current-round contributions never leak into peer prompts.
- Partial rounds, unrelated tools, model retries and duplicate results cannot
  advance state; wrong-round, changed duplicate and unknown participant fail.
- Failure, empty/truncated result, cancellation and JSON commit failure prevent
  partial publication, participant memory and synthesis for that round.
- A new debate ignores prior peer arguments and removes stale final decisions.
- Next-round prompts and manager synthesis include all accepted history; risk
  debators receive the same persisted history as the manager.
- Offline real Strands invocations verify staging, synthesis and hook ordering.
- Both distributed variants fail explicitly; public tool signatures/ports stay.

## Tasks

- [x] Implement policy, state machine, round context and runner.
- [x] Integrate manager/participant hooks, constructors, contracts and prompts.
- [x] Add offline state, scheduler and Strands integration tests.
- [x] Run checks and record validation evidence.

## Validation evidence

- `python -B -m unittest discover -s tests -v`: 39 tests passed, including
  15 debate tests covering pure state, real SDK invocations, streaming and the
  public ResearchManager/RiskManager tools with scripted offline models.
- Acceptance verifies matching snapshots and published state during each round,
  transcript independence from execution order, delayed memory writes, partial
  failure/cancellation, failed JSON commits, and fresh invocation cleanup.
- `uv run pre-commit run --all-files` and checks explicitly including new debate
  modules, tests and this spec: all applicable checks passed.
- `git diff --check`: passed.

No live model, memory backend, HTTP A2A server or market-data API was used.
