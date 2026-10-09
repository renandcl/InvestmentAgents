# Feature specification: Run isolation

**Feature:** 001-run-isolation
**Status:** Implemented and validated offline; see evidence.md
**Prepared:** 2026-10-04
**Reviewed:** 2026-10-09 against c51be7f plus the run-isolation implementation
**Input:** Prepare a specification for run isolation using spec-driven development.

## Problem and outcome

At the committed c51be7f baseline, analyses coordinate through one mutable JSON file, share memory and provider caches, and write reports named only by ticker/date. Repeated or concurrent executions can interfere, and partial failures lack a reliable run record.

Every execution must instead own its mutable state and resources. Identical ticker/date inputs must produce independent, inspectable runs. This feature establishes application-level isolation among trusted executions; it is not an OS security boundary or proof of point-in-time financial correctness.

## Updated baseline

Build on the implemented [hook contracts](../002-agent-hook-contracts/spec.md) and [participant-aware debates](../003-participant-debates/spec.md). Their shared AgentLifecycleHooks, AGENT_SPECS registry and DebateRunner are integration points, not work to rebuild. Spec 003 supersedes spec 002's earlier tool-result-turn counting. Preserve opening/rebuttal/clarification, quorum, shared prior-round snapshots, conversation resets and one manager synthesis.

The committed baseline uses JsonReportStore: atomic file replacement does not make its read-modify-write operation transactional across concurrent writers. The run-isolation implementation integrates RunStore through agents, hooks, debate runner and entry points. See evidence.md for all 27 acceptance scenarios and implementation-progress.md for delivered behavior and limits.

## Scope and assumptions

In scope: root in-process workflow, standalone agent examples, run identity, state, sessions, memory policy, mutable provider caches, lifecycle, artifacts, failure propagation and owned-resource cleanup.

The runtime supports concurrent independent runs in one process and separate processes on the same host using a local filesystem. The current batch loop stays sequential. Shared SimFin downloads are read-only during execution; data acquisition remains an offline operation.

Memory defaults to OFF. RUN_ONLY is the only enabled-memory option: it never imports or retrieves another run's memories.

For the isolation release, all A2A constructors, servers and manual clients must reject execution before side effects. This extends the existing research/risk distributed-constructor guards; spec 003 currently permits A2A servers wrapping in-process managers, so the additional restriction must be explicitly documented. Distributed run-context propagation, shared server ownership and multi-host coordination are a separate feature. No port changes are required.

Out of scope: changing financial prompts or roles, full financial-stage enforcement, temporal-data validation, experiment-memory reuse, model/provider upgrades, trading simulation, broker execution, scheduling, automatic crash recovery, resume and retention/deletion.

Existing global data, sessions, caches, memories and reports remain untouched. There is no automatic migration or legacy fallback. Package caches/model weights may remain shared only when they do not carry analysis state. Network filesystem semantics are unsupported.

## User stories

### US1 - Repeat analyses independently (P1)

As a researcher, I can repeat the same ticker/date and keep each execution's inputs, status and outputs separately.

Acceptance: two runs with identical inputs have different identities and mutable paths; both reports survive and no planted sentinel crosses between runs.

### US2 - Preserve concurrent results (P1)

As a researcher, I can run independent analyses concurrently and retain all committed agent reports within each run.

Acceptance: barrier-controlled writes from different agents retain both report values; interleaved runs and spawned processes cannot exchange state or overwrite each other's output.

### US3 - Inspect failure and stop owned resources (P1)

As an operator, I can identify a failed/cancelled execution and stop it without affecting another run.

Acceptance: a failure during agent construction after one MCP starts records a failure and closes acquired resources while another run completes.

### US4 - Control memory use (P2)

As a researcher, I can disable memory entirely or confine it to one execution.

Acceptance: OFF never initializes memory inference or storage; RUN_ONLY retrieval is restricted by run and agent, including auxiliary history storage.

### US5 - Use consistent entry points (P2)

As a developer, standalone examples follow the same contract and unsupported distributed paths fail clearly.

Acceptance: examples allocate fresh contexts; A2A entry points reject before constructing agents, writing legacy files or opening network connections.

## Functional requirements

| ID | Requirement |
|---|---|
| FR-001 | Allocate a fresh opaque run ID for every execution. Identical inputs do not reuse identities. A collision must fail without altering existing files. |
| FR-002 | Validate inputs and persist immutable identity/configuration before model, MCP or memory initialization. |
| FR-003 | Supply run context from trusted host code to all agents, hooks, session/memory adapters and MCP children. Missing or mismatched context must fail without global-path fallback. |
| FR-004 | Keep all application-controlled mutable artifacts within run-scoped roots. Model output, raw ticker strings and search queries must not determine filesystem paths. |
| FR-005 | State updates must be atomic patches. Concurrent distinct-key writes must survive; readers must not observe partial commits; stale same-key writes must fail. |
| FR-006 | Replaying an identical report operation must be idempotent. Reusing its operation ID with different content or ownership must fail. A later genuine invocation can replace its own report. |
| FR-007 | Agent conversations and sessions must be fresh per run. Concurrent use of the same stateful agent instance must be serialized. |
| FR-008 | OFF must perform no memory initialization, inference or persistence. RUN_ONLY must isolate vector stores, history stores and retrieval by run and agent. |
| FR-009 | MCP children must receive explicit private cache roots without parent environment/CWD mutation. Fresh and cached paths must not access another run's mutable cache. |
| FR-010 | Persist lifecycle status, timestamps and structured errors. Success requires completed invocation, the required root report, successful cleanup and committed final artifacts. A failure in an owned agent invocation must prevent run success even when an SDK tool boundary converts the exception into an error result and the root model continues. |
| FR-011 | Normal completion, catchable startup/invocation failure and cancellation must clean up owned resources. Cleanup is idempotent and never closes another run's resources. |
| FR-012 | Publish final state and Markdown under the run directory with identity and hashes. Terminal runs reject new writes and re-execution. |
| FR-013 | Root workflow and standalone examples use the same run factory. A2A and any unsupported direct service entry point fail before side effects. |
| FR-014 | New executions do not read analysis state from, modify, import or delete legacy global artifacts. Shared read-only datasets are the explicit exception. |
| FR-015 | Manifests and structured diagnostics exclude credentials, authorization headers, credential-bearing URLs and environment dumps through an allowlist. |
| FR-016 | Callers receive run identity, outcome and committed artifact locations; failures propagate as errors with run identity, not only printed messages. Failure before durable allocation is an initialization error. |
| FR-017 | Resolve paths beneath configured local roots. Reject invalid IDs, traversal and pre-existing symlink/junction escapes before touching targets. |
| FR-018 | Record memory mode, model IDs, code revision/dirty status, prompt hashes and lockfile hash when available. Explicitly represent missing provenance; a recorded seed does not promise deterministic generation. |
| FR-019 | Reuse AgentSpec/AGENT_SPECS and the shared lifecycle for validation, input defaults/refresh, extraction, declared outputs and memory formatting. Bind a run store through that shared boundary; preserve both trader and risk-manager aliases. |
| FR-020 | Bind every debate/round context to its run and manager invocation. Atomically reset only the declared debate outputs at a fresh invocation, and atomically publish a full quorum's reports, complete history and round receipt. Reject foreign contexts, overlapping same-manager debates, stale generations and conflicting duplicates without altering committed state. |
| FR-021 | Participants stage results without live publication or memory writes. Store memories only after report/round commit. Failed commits produce no memory writes; post-commit memory failure preserves committed data and prevents synthesis/run success. Store-operation replay must not retry external memory side effects. |

## Nonfunctional requirements

- NFR-001: Use the existing Python >=3.13 and Strands stack; work on Windows local storage without a new network database.
- NFR-002: Mandatory acceptance is offline unittest with temporary directories and fake models/providers/processes.
- NFR-003: Storage contention has a finite timeout; never hold state locks across model/network calls.
- NFR-004: Audit auxiliary vendor persistence and initialization side effects, not just application filenames. Run-dependent routing cannot use mutable process globals.
- NFR-005: An uncatchable termination can leave a nonterminal run. File presence never proves success; automatic recovery and guaranteed cleanup after hard kill are excluded.
- NFR-006: Preserve the c51be7f financial prompts, declared report keys/aliases and spec 003 debate semantics. Adapt the current 39-test suite across five test modules without weakening behavioral guarantees. Replace obsolete JSON-specific integration expectations with equivalent RunStore failure tests, retaining standalone legacy-adapter tests where useful.

## Success criteria

All scenarios AT-01 through AT-27 in acceptance.md pass, including task/process concurrency and fault injection. Existing regression tests and required formatting checks pass. A path audit proves supported entry points have no executable legacy mutable-path fallback. A2A restrictions and memory defaults are documented.

Zero observed contamination in these tests is the release gate; it is not a claim of proof against arbitrary malicious code or hardware failure.

## Specification maintenance

Implementation must follow [contracts](contracts.md) and [plan](plan.md). Change requirement and acceptance IDs before changing intended behavior. The task list tracks implementation separately from specification readiness.

Future work must explicitly specify any experiment-scoped memory or shared cache reuse; neither may be introduced as an optimization that bypasses this contract.
