# Technical plan: Run isolation

**Status:** Implemented and validated offline on 2026-10-09. [spec.md](spec.md) defines required outcomes; [evidence.md](evidence.md) records the acceptance audit.

## Architecture

Keep the existing Strands agent tree and the shared agents/hooks contracts, services and lifecycle added in spec 002. Preserve the agents/debates state machine and runner added in spec 003. The runtime package now separates context, transactional storage, agent invocation boundaries, lifecycle/resources, memory workers, MCP setup, caches and artifacts. A RunRuntime owns context, state, session construction, memory factory and resource lifetime. Agent constructors receive dependencies explicitly and pass them to children.

The LLM cannot choose context, run IDs, storage paths or lifecycle transitions. No mutable global "current run", parent os.environ change or chdir is allowed.

## Baseline and dependencies

Target c51be7f, including a78e134 (dependencies), 7ec5032 (hook contracts), and c51be7f (participant debates). The locked and installed versions checked on 2026-10-08 are Strands 1.57.2, Strands tools 0.8.9, Mem0 2.2.1, Chroma 1.5.9 and pandas 3.0.6. Preserve the blank-environment fallback behavior verified in test_model_configuration.py.

Reuse AgentSpec, StateField, MemoryPolicy, DebatePolicy, ParticipantSpec, PromptRenderer and extract_report. Inject the new repository into AgentLifecycleHooks and DebateRunner; the 13 hook.py files remain thin contract selectors. Do not recreate thirteen storage implementations or the removed StoreMemoryHook. JsonReportStore may remain for legacy adapter tests, but no isolated runtime can fall back to it.

## Storage layout

```text
data/runs/<run_id>/
  run.sqlite3
  manifest.json
  shared_document.json
  report.md
  sessions/<agent_id>/<session_id>/...
  memory/<agent_id>/chroma/...
  memory/<agent_id>/history.sqlite3
  cache/<provider_id>/...
  diagnostics/...
```

run.sqlite3 is authoritative. JSON files are derived exports, never live coordination. The default root is resolved from the repository root. Agent/provider names come from registered identifiers; filenames never contain raw tickers or queries. Existing reports/ is not the new output destination.

## Transactional state

Use standard-library sqlite3, one database per run, on local disk. Use short transactions, per-operation connections, foreign keys, rollback journaling, a conservative durability setting and a configurable bounded busy timeout (default 5 seconds).

Persist identity, lifecycle, report-key revisions, idempotency receipts and events together. Atomic patches compare revisions per affected key, so unrelated reports do not conflict. Derive write ownership from AGENT_SPECS rather than a second hardcoded registry. Ordinary hooks publish only their declared output_keys; commit trader_report/trader_investment_plan and risk_manager_report/final_trade_decision aliases atomically. DebateRunner needs a separate manager-scoped round-commit capability to publish participant-owned outputs and the policy history_key; never grant managers unrestricted patch access.

Checking RUNNING and committing a patch occur in the same transaction. Terminal runs reject new operations. Identical operation replay returns the original receipt without another event. A changed payload with an existing operation ID fails. Do not retry stale reports by blindly overwriting newer content.

AgentLifecycleHooks reads consistent snapshots and preserves declared input defaults/refresh, pure rendering and successful-result extraction. Identity fields are never writable report keys. Add a typed repository boundary in the shared layer: explicit read_snapshot/patch_reports/begin_debate/commit_round operations, with run context supplied separately. A raw read()/patch(changes, remove_keys=...) shim alone cannot carry revision, writer and generation checks.

Debate reset requires transactional deletion. Keep per-key tombstone revisions so deleting/recreating a key does not reset its revision to zero and allow an old write. The shared_document_file state attribute must not point consumers at a writable coordination file; remove executable uses or expose an explicitly export-only path. This remains a storage refactor, not a typed financial-decision schema.

## Debate transactions and snapshots

Keep DebateState's quorum validation and canonical history ordering. Keep local participants sequential as today, with copies of the same frozen prior-round snapshot. Preserve six research contributions, nine risk contributions and one synthesis per manager.

Before any participant/model/memory work, validate manager run identity and acquire its invocation ownership. Atomically begin a new debate, generate its debate_id, reset only its participant reports, history and manager output aliases, and capture the opening snapshot from that transaction. Do not pass a pre-reset snapshot read outside the transaction. Preserve unrelated analyst/trader state.

Extend RoundContext with run_id, manager_id, manager_invocation_id and snapshot/round revision. Validate them at the hook boundary before reading a staged snapshot, formatting a prompt or retrieving memories. No mutable global context and no model-supplied identity. Reject overlapping invocations for one manager slot even when different Agent instances/processes use the same run store; research and risk slots remain distinct.

Participants keep staging in memory. On quorum, commit all participant reports, the entire accepted history, the round index and its idempotency receipt in one transaction. Validate current run status, active debate generation, expected round, participants and revisions. Synthesis may publish its manager outputs only for the active generation after all three committed rounds. Late callbacks from a previous debate cannot repopulate reset keys.

Preserve commit-before-memory ordering. A failed commit writes no participant memories. A memory failure after commit retains the full committed round, aborts that invocation and blocks synthesis; already written external memories are not rolled back. The store receipt covers database effects only. Do not add automatic retries or an exactly-once claim for Mem0. A duplicate receipt does not trigger another memory write.

End manager invocation ownership explicitly on completion, failure or cancellation; old callbacks remain fenced by their generation. An ownership record left active by hard kill cannot be stolen automatically. A new invocation of a completed/aborted debate in a still-running run receives a fresh generation and reset; a terminal run cannot restart.

Preserve conversation clearing at every participant invocation and each new manager debate. Any same-agent lock must enclose those clears, invocation hooks, invocation/stream consumption and finalization, rather than locking only the public tool method or invoke_async. Use a non-reentrant boundary shared by supported invocation paths; cancellation releases it after cleanup. Retain stream_async, direct invocation and public manager tool acceptance.

## Context, agents and sessions

Validate RunConfig before side effects; allocate a UUID directory exclusively and record CREATED before model/MCP/memory construction. RunContext is frozen and includes validated identity and resolved roots. Resolve model configuration once per run; credentials stay in memory and are not serialized.

Require explicit keyword-only runtime dependencies for all agents. Bare constructors fail clearly rather than discovering the old shared JSON. Every child inherits its parent's context/store/resource registry.

Construct FileSessionManager under the run's registered agent path. Reuse a session only where the agent's existing lifecycle permits it; spec 003 clears participant conversations each invocation and manager conversations each new debate even within one run. Serialize calls to the same mutable agent instance; independent agents and runs may progress concurrently.

## Memory

OFF is implemented as a non-null NullMemory satisfying AgentLifecycleHooks' existing memory-service contract: search_memories returns no records and add_memory performs no work. It does not instantiate Mem0, embedding clients or stores. Avoid imports that initialize persistent memory as a side effect.

RUN_ONLY supplies separate per-run/per-agent Chroma and explicit history_db_path locations. Use run-scoped user identity and registered agent identity for retrieval as a second boundary. Audit auxiliary stores in the pinned library. No legacy import, experiment-wide collection or mutable global MEM0_DIR switch is allowed.

Implementation audit: Mem0 2.2.1 imports mem0.memory.setup, which creates MEM0_DIR and may read/write vendor configuration. RUN_ONLY therefore uses one owned child process per run/agent, with child-only MEM0_DIR under memory/<agent>/vendor and telemetry disabled before import. The parent never imports Mem0 for memory adapters or changes its environment; explicit Chroma/history paths remain mandatory. The worker uses a narrow request protocol and closes with the run.

Preserve the Mem0 2.2.1 filters/top_k API now used by all memory adapters: search(..., filters={...}, top_k=n_matches) and get_all(filters={...}). Replace ticker-only user scoping with a run/agent-bound identity and test that queries cannot omit that scope. Keep existing memory prompts/model settings unless needed to eliminate a persistence escape. Isolation does not grant temporal correctness to generated memories.

## MCP integration and cache safety

Pass INVESTMENT_RUN_ID and INVESTMENT_CACHE_ROOT through StdioServerParameters.env. The cache root is an absolute provider-specific directory. Keep repository-root CWD and existing server credential delivery. Reserved host context must win over child --env-file configuration; conflicting values fail before startup.

Migrate Yahoo, both Stockstats cache paths, Finnhub news/insider services, Reddit and DuckDuckGo. Canonical cache keys hash provider/version/method/arguments. Use unique temporary files plus atomic same-directory replacement; concurrent writers cannot expose torn content. Malformed entries cause a named failure or explicitly recorded refetch, not partial parsing.

Windows contention applies to both publication and reads. Both use a one-second bound for transient sharing/permission failures, with path containment rechecked on each attempt. The existing complete file remains until replacement succeeds; permission errors are never cache misses and persistent failures propagate. Deterministic fault injection covers transient recovery and deadline exhaustion alongside concurrent-reader/writer tests.

SimFin CSVs remain read-only shared inputs, never updated by analysis. Google News, Mem0 MCP and direct provider demonstrations must adopt explicit context or fail before service construction. Include library-owned analysis caches in the persistence audit.

A resource registry registers a cleanup wrapper before each start attempt, so partial acquisition is covered. Cleanup is safe for unstarted/partially started resources, executes in reverse order, continues after individual errors and preserves the original error. Stop only owned client/process handles. The installed MCPClient exposes stop/context-manager cleanup.

Cancellation stops accepting new invocations and cancels/drains owned work before final state publication. Shield cleanup from ordinary task cancellation with a finite configurable deadline (default 30 seconds for run cleanup). On timeout, record CleanupTimeout and close/terminate only provably owned resources using supported APIs. Never kill all processes by name.

## Lifecycle and finalization

CREATED -> RUNNING -> SUCCEEDED / FAILED / CANCELLED. CREATED can also fail or be cancelled. Terminal states are immutable.

Construction is inside the managed failure boundary. On success:
1. Await root invocation and owned child work; require the designated root report and no recorded owned-agent failure.
2. Close owned resources successfully.
3. Export a consistent state snapshot and render report.md via UTF-8 temporary files and atomic replacement.
4. Hash artifacts and commit their receipts and SUCCEEDED together in SQLite.
5. Refresh the human-readable manifest.

Database and filesystem writes are not one transaction. Files created before step 4 are not successful artifacts unless the database says so. Inspection trusts SQLite. A missing/stale manifest is regenerable; failure to refresh it after committed success is a derived-export warning, not a contradictory state transition.

Catchable construction/invocation/cleanup/report-export failures record FAILED. Cancellation records CANCELLED with cleanup errors and propagates cancellation to the caller. A status-write failure reports outcome unknown and preserves available files. Hard kill can leave CREATED/RUNNING; there is no automatic resume, takeover or success inference.

Strands 1.57.2 can convert a tool exception into a tool error result and let the calling model continue. Therefore a root end_turn is insufficient evidence that child invocations succeeded. Record an owned-agent failure at the runtime invocation boundary before it crosses the SDK tool boundary, retain safe agent/invocation attribution, and check that record before success publication. A post-commit memory failure must remain fatal to the run even if the parent subsequently emits a valid report. Keep the committed round for diagnosis and complete owned cleanup. This is a run-local failure record, not a global flag or a rule that every recoverable provider tool error is fatal. Caller cancellation must retain cancellation semantics.

SUCCEEDED means infrastructure completion, not that every optional analyst participated or the financial recommendation is correct.

## Entry points and compatibility

- main.run_analysis retains ticker/date convenience inputs and delegates to RunRuntime. Return RunResult on success; otherwise raise RunExecutionError carrying run identity.
- Batch execution may continue after a failed item but aggregates results and exits nonzero if any item fails.
- Standalone agent __main__ examples allocate fresh runtimes and finalize against that agent's designated report key.
- Keep the existing early research/risk distributed guards and extend coverage to the other two distributed variants, A2A server factories and manual clients. Normalize UnsupportedExecutionMode as a ContractError-compatible error if needed to preserve current callers/tests. The all-A2A restriction intentionally goes beyond spec 003, whose servers wrapping local participants currently remain supported; document this compatibility change prominently. Keep ports unchanged.
- Direct MCP examples require explicit child context or reject startup. Standalone memory demonstrations use the common fresh-run bootstrap.
- Keep one snapshot-driven report renderer (currently runtime/artifacts.py). Migrate utils/report.py to that explicit contract or retire its legacy entry point with an early guard. Its current __main__ reads data/shared_document.json and must not remain a supported fallback. Rendering/publication failures propagate.
- Update README and repository instructions. Preserve legacy artifacts and financial prompts. The renderer enumerates declared primary output keys, so it includes the news report and avoids duplicate alias sections; this does not change financial reasoning.

## Integration inventory

| Surface | Change |
|---|---|
| main.py | Run ownership, durable status, outcome propagation |
| 13 agent.py implementations | Explicit context, child propagation, sessions/resources |
| agents/hooks lifecycle/services + 13 thin hook.py selectors | Inject RunStore centrally; preserve AGENT_SPECS contracts and finalization ordering |
| agents/debates runner/state | Run-bound round contexts, atomic reset/quorum commit, generation fencing and memory ordering |
| Five agent memory.py implementations | OFF/RUN_ONLY and vector/history isolation |
| Four a2a_agent.py variants and all A2A servers/clients | Fail before side effects |
| MCP services/utilities/demos | Explicit roots, atomic safe cache paths or startup guard |
| runtime/artifacts.py and utils/report.py | One snapshot renderer; remove or guard the legacy report demo |
| Five existing test modules + isolation tests | Preserve 39 current tests' semantics; adapt repository fixtures and add round-isolation coverage |

## Delivery

Build the runtime and debate-capable store contracts first, then inject them through the shared hooks/runner before migrating agents/memory, MCP caches, entry points and reporting. Plain report patches alone are not a usable migration target for the current DebateRunner. Partial changes must not advertise complete isolation. Keep dependencies pinned unless a demonstrated incompatibility requires a documented specification change.

Run offline unittest and the current pre-commit configuration (Ruff with import sorting, Black, secret detection and file checks) from repository root. Include the new runtime package in Ruff's first-party configuration when introduced. Live API/model smoke tests are supplementary. No requirement here authorizes live trading or automatic historical-data downloads.

## Update-review findings resolved

1. Close the run-status gap across SDK tool boundaries (T004/T013/T023); extend AT-10/AT-25 with a parent that continues after its child fails.
2. Fix bounded Windows cache-read contention and test deadline exhaustion (T011/T017, AT-07).
3. Complete the acceptance cases that component tests do not yet establish: interleaved research/risk debates across two runs, concurrent readers during quorum publication, duplicate-receipt memory suppression and queued manager conversation resets (T024, AT-22..26).
4. Verify real installed Mem0/Chroma persistence with offline inference substitutes; finish credential/provenance and unsupported-entry-point audits, including the legacy report demo (T008/T012/T019, AT-06/AT-13/AT-16/AT-20).
5. Update repository usage instructions and reconcile public contract signatures with the final implementation. Run all regression tests and pre-commit on tracked and new files, then record evidence per acceptance scenario (T020).

All five follow-ups above are implemented and verified. The runtime, thirteen agents, provider migration and entry-point integration are covered by 98 offline tests, the quality gate and the audit in evidence.md. The original task IDs are retained for traceability.
