# 005 - Persistent memory with isolated execution

**Prepared:** 2026-10-25
**Status:** Implemented and validated offline; see [evidence](evidence.md) and [tasks](tasks.md).
**Extends:** [spec 001](../001-run-isolation/spec.md) FR-008, FR-012 and US4, which define the memory worker, its private vendor imports and the success commit used here.

## Outcome

The bull, bear, research-manager, trader and risk-manager prompts ask each agent to
learn from `{past_memories}`. With memory `OFF` or `RUN_ONLY`, that slot holds nothing
from earlier analyses. This spec restores long-term Mem0/Chroma memory by default, so
these agents see what they extracted in earlier successful analyses of the same
ticker. Each run still keeps private, writable Mem0 vector, history and vendor stores;
runs share only read-only, hash-committed text snapshots. Short-term
conversation/debate state is unchanged.

This replaces spec 001's original `OFF` default and its ban on cross-run memory reuse.
As a result, two runs with identical inputs are no longer independent (spec 001 US1):
what each sees depends on earlier successful runs in the same output root. Legacy
global memories remain untouched.

Out of scope: reconciling conflicting facts, memory compaction or retention policy,
sharing across tickers, agents, output roots or experiments, and migrating legacy
memory.

## Requirements

- PM-001: `PERSISTENT` is the default `memory_mode`. `OFF` creates no Mem0 instance or
  memory worker; `RUN_ONLY` keeps strict run/agent isolation without cross-run reads
  or publication.
- PM-002: A persistent worker uses its existing private run/agent paths and filters.
  Seed its vector store from extracted memories of the same agent and exact ticker,
  in the same output root. Re-embedding uses the run's configured embedding model.
- PM-003: Sources must be `PERSISTENT` runs with committed `SUCCEEDED` status, an
  analysis date strictly before the target date, and completion before the target's
  creation. Never use same-date, future, active, failed or cancelled runs. Record
  source run IDs and snapshot hashes in the run's `memory/<agent>/seed.json` before
  starting the worker. `seed.json` is a hand-off file, not a hash receipt; durable
  provenance is the `sources` list in the committed snapshot.
- PM-004: Snapshot extracted memories after additions. Commit snapshot hashes in the
  same success transaction as final report/state hashes, only after workers close.
  Validate identity, scope, schema, length and hash on reuse. A corrupt or unreadable
  source fails the target run. The scan currently validates every run directory in
  the output root before filtering by mode and ticker, so one damaged or locked run
  fails every `PERSISTENT` start in that root until the run is removed or repaired.
  No legacy fallback, automatic migration or shared mutable index.
- PM-005: Import seeds into the private store with `infer=False` (stored verbatim, no
  LLM fact extraction); memory extraction from the current report keeps `infer=True`.
  Scoped `search`/`get_all` and fatal worker errors are unchanged.
- PM-006: Each snapshot lists its direct sources. An eligible snapshot is superseded
  when another eligible snapshot lists it; the others are lineage heads. Seeds are the
  deduplicated union of the heads' texts. Along one chain, a descendant replaces its
  parent, so facts it updated or deleted do not return. Facts held by sibling branches
  can coexist or reappear (add-wins).
- PM-007: Every memory carries the analysis date of the run that extracted it, in the
  store and in snapshots (version 2). Older version 1 snapshots are not reused. Retrieval takes up to 100 nearest candidates, ranks them by
  similarity × 0.5^(age in days / recency half-life, default 90 days) and gives the
  agent at most 10. PM-003 and PM-008 already keep later-dated and out-of-window
  memories out of the store.
- PM-008: Seeds include only memories within the lookback window (default 365 days)
  of the target run's analysis date. Source snapshots, merged seeds and exported
  snapshots each hold at most 9,999 memories. Reaching 10,000, the retrieval limit,
  fails rather than silently truncating.

## Acceptance

- A1: `PERSISTENT` is the default; explicit `OFF` does not initialize Mem0 or a worker.
- A2: With real Mem0/Chroma and the deterministic offline embedding/inference fixture,
  a later run retrieves earlier successful memory through its own private
  vector/history/vendor stores and its own run/agent filters.
- A3: Other tickers/agents, same/future dates, `RUN_ONLY`, failed/active/cancelled
  runs and sources finishing after target creation do not contribute seeds.
- A4: Multiple eligible source branches merge, and exact duplicate texts appear once.
- A5: A descendant's snapshot replaces its ancestor's; a fact the descendant deleted
  does not return.
- A6: An export reaching 10,000 memories fails instead of truncating.
- A7: Corrupt snapshots fail closed. A failed success commit publishes no reusable
  memory, and a hard-killed run stays nonterminal, so it is never an eligible source.
  A snapshot whose content no longer matches its recorded hash blocks the success
  commit and is rejected on later reuse.
- A8: Source files remain byte-identical after retrieval. The parent process never
  imports Mem0 or changes environment variables or the working directory. Existing
  isolation, debate and cleanup tests pass.
- A9: Retrieval returns at most 10 memories and ranks a recent memory above
  an older one of equal similarity.
- A10: Seeds exclude source memories dated outside the lookback window.

## Tradeoffs and risks

- Alternatives: Opt-in `PERSISTENT` would keep run independence but leave
  `{past_memories}` empty by default. A shared Mem0/Chroma store would avoid
  re-embedding but reintroduces the shared writable store spec 001 removed. Seeding
  from the single latest snapshot would avoid PM-006's add-wins rule but drops memory
  from concurrent or backfilled branches.
- Retention: Remove memory only by removing whole run directories, newest-first.
  Editing files inside a run is corruption (PM-004); removing a run that another run
  descends from revives the facts it replaced.
- Growth and cost: Each start re-embeds its windowed seed with the local embedder
  (Ollama `qwen3-embedding:0.6b`). If an agent/ticker extracts more than 9,999
  memories within one window, its `PERSISTENT` runs fail until the window passes;
  use `RUN_ONLY`/`OFF` or shorten the window. There is no compaction.
- Integrity: Hashes live in each source run's own SQLite file, so they detect
  accidental damage, not deliberate tampering.
- Memory poisoning: Facts extracted with `infer=True` from reports built on untrusted
  news and Reddit content now carry into later runs by default.
- Point in time: A backdated run executed today can store present-day tool data under
  a past analysis date, which later runs inherit. Date filtering also cannot remove
  future knowledge already in model weights.
