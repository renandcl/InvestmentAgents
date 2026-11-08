# 005 - Persistent memory with isolated execution

**Prepared:** 2026-10-25
**Status:** Implemented and validated offline; see [evidence](evidence.md).

## Outcome

Restore long-term Mem0/vector memory by default without sharing writable vendor,
Chroma or history stores between executions. Short-term conversation/debate state
is unchanged. This supersedes spec 001's OFF default and prohibition on explicit
cross-run memory reuse; legacy global memories remain untouched.

## Requirements

- PM-001: PERSISTENT is the default. OFF remains inert; RUN_ONLY retains strict
  run/agent isolation without cross-run reads or publication.
- PM-002: A persistent worker uses its existing private run/agent paths and filters.
  Seed its vector store from deduplicated extracted memories of the same agent and
  exact ticker, in the same output root. Re-embedding uses the current memory model.
- PM-003: Sources must be PERSISTENT runs with durable SUCCEEDED status, an analysis
  date strictly before the target date, and completion before the target's creation.
  Never use same-date, future, active, failed or cancelled runs. Pin source identities
  and hashes in the current run's seed artifact before starting the worker.
- PM-004: Snapshot extracted memories after additions. Commit snapshot hashes in the
  same success transaction as final report/state hashes, only after workers close.
  Validate identity, scope, schema, length and hash on reuse; fail closed on corrupt
  eligible sources. No legacy fallback, automatic migration or shared mutable index.
- PM-005: Import seeds with infer=False into the private store; current report memory
  extraction keeps infer=True. Preserve scoped search/get_all and fatal worker errors.
  Merge eligible lineage heads so concurrent successful branches are retained;
  do not reintroduce ancestor facts that a descendant has updated or deleted.
  Deduplicate text; cap each snapshot at 10,000 memories and fail rather than silently
  truncating an export at that boundary.

## Acceptance

1. PERSISTENT is the default; explicit OFF does not initialize Mem0 or a worker.
2. Real offline Mem0/Chroma: a later run retrieves earlier successful memory through
   its own private vector/history/vendor stores and its own run/agent filters.
3. Other tickers/agents, same/future dates, RUN_ONLY, failed/active/cancelled runs and
   sources finishing after target creation do not contribute seeds.
4. Multiple eligible source branches merge and exact duplicate texts appear once.
5. Corrupt snapshots fail closed. Failed success commits and hard kills do not publish
   reusable memory. Altered snapshot hashes prevent success commit or later reuse.
6. Source files remain byte-identical after retrieval; no parent Mem0 import or
   environment switching occurs. Existing isolation/debate/cleanup tests still pass.

## Tradeoff

Successful run directories retain their memory snapshots. Removing them removes
that memory history. Initializing a new persistent store re-embeds imported text;
this avoids a shared writer/service and keeps embedding versions compatible, but
has a cost that grows with retained memory. This filters stored knowledge by source
analysis date; it cannot remove future knowledge already present in model weights.
