# 002 - Explicit agent hook contracts

Status: Implemented and validated offline. Prepared: 2026-10-07.

## Problem

Each agent duplicates state loading, prompt formatting, report extraction and
memory handling. Inputs, defaults, output aliases and debate transitions are
implicit in hook code and prose. It is difficult to review or validate a change.

## Scope and requirements

1. Every agent has an immutable Python contract declaring its identity, prompt,
   state inputs (source, default, required/optional, refresh timing), prompt
   bindings, output keys, optional memory policy and optional debate policy.
2. Validate contracts and prompt placeholders when constructing hooks. Required
   ticker and current_date values must be nonempty strings before invocation.
   Reports remain optional for compatibility with standalone agent examples.
3. One shared lifecycle provider owns load -> prepare -> render -> finalize.
   Prompt rendering never changes workflow state. Always render the original
   template, including after retries and repeated invocations.
4. Preserve the existing debate unit: one successful tool-result turn advances
   one round, deduplicated by toolUseId, with synthesis after three rounds.
   Declare this limitation explicitly; participant-aware rounds and deterministic
   top-level orchestration are deferred. Preserve existing financial prompts.
5. Finalize only a successful, nonempty assistant result belonging to this
   invocation. Extract all text blocks and remove think blocks once. Persist
   declared output keys together, then store the same report in memory. Failed,
   cancelled, interrupted or incomplete invocations cannot store a report/memory.
6. Retain all per-agent hook.py entry points and migrate both in-process and A2A
   constructors to one provider, removing the separate StoreMemoryHook.
7. Bind risk peers to their actual canonical report keys. Repeated invocations
   must clear absent peer inputs rather than retain stale arguments.

## Design

agents/hooks/contracts.py defines frozen StateField, MemoryPolicy,
ToolResultTurnPolicy and AgentSpec data classes. agents/hooks/specs.py declares
all thirteen agent contracts. Local hook.py files select their contract.
agents/hooks/services.py contains template validation/rendering, JSON access,
report extraction and memory formatting. agents/hooks/lifecycle.py adapts these
services to Strands events with explicit finalization ordering.

The JSON repository remains the storage adapter. It is not run isolation or
cross-process transactional storage. Spec 001 stays proposed and unchanged;
its future RunStore can replace the adapter without changing agent contracts.
Risk history retains its current local-manager behavior in this refactor.

## Acceptance

- All thirteen templates validate against their declared bindings; unknown,
  malformed or unsafe placeholders fail at construction with agent context.
- Missing required identity fails before memory retrieval/model execution;
  missing optional reports use declared defaults, including on reinvocation.
- Rendering twice preserves workflow state and handles braces in report text.
- Existing three-round/retry behavior and research -> trader data flow pass.
- Risk peer prompts consume canonical published reports.
- Finalization handles mixed content, multiple text blocks and think blocks;
  failed/incomplete results cannot reuse an older assistant message.
- JSON failure prevents memory writes; memory receives exactly the persisted
  report after JSON success. Output aliases are written together.
- Real Strands hook registration invokes the shared lifecycle in order.
- In-process and A2A constructors register one provider per agent.

## Implementation tasks

- [x] Add contracts, shared services and lifecycle adapter.
- [x] Declare and migrate all agent profiles and both constructor paths.
- [x] Add offline acceptance tests and update existing hook regressions.
- [x] Run unittest suite, pre-commit checks and diff checks; record evidence.

## Validation evidence

- `python -B -m unittest discover -s tests -v`: 24 tests passed, including
  15 new acceptance tests in tests/test_hook_contracts.py.
- `uv run pre-commit run --all-files`: all applicable checks passed.
- `uv run pre-commit run --files <changed and new files>`: all applicable
  checks passed, including the new untracked modules, tests and specification.
- `git diff --check`: passed.

No live model, memory backend, MCP API or A2A server was invoked. Lifecycle
acceptance uses the installed Strands registry/events with offline agent stubs.
