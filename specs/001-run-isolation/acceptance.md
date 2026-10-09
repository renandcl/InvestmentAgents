# Acceptance scenarios

**Status:** Passed in the 2026-10-09 offline acceptance audit. The final working-tree suite passed all 98 tests in 38.308 seconds. See evidence.md for test/source evidence per scenario and the implementation limits.

| ID | Scenario and expected outcome | Requirements |
|---|---|---|
| AT-01 | Execute identical inputs twice. All mutable identities/roots differ, both reports remain, and cross-run sentinels are absent. | FR-001, FR-003, FR-004, FR-007, FR-012 |
| AT-02 | Inject an already allocated run ID. Reject creation and leave existing bytes unchanged. | FR-001, FR-014 |
| AT-03 | Interleave two runs with barriers in one event loop, then spawned processes. State, sessions, cache output and errors remain attributed correctly; parent env/CWD do not change. | FR-003, FR-004, FR-007, FR-009 |
| AT-04 | Concurrent distinct-key writes within one run, from threads and spawned processes, preserve both commits. Readers never observe partial state. | FR-005 |
| AT-05 | A stale same-key patch fails; identical operation replay is idempotent; changed-payload replay fails. Trader and risk-manager reports commit with their respective aliases. | FR-005, FR-006 |
| AT-06 | OFF creates no memory client/store/inference. RUN_ONLY retrieves A's sentinel in A, never B for the same ticker/agent. Verify Chroma and history paths. | FR-008 |
| AT-07 | Two MCP children cache distinct fake results for identical inputs and see only their own data. Concurrent same-run cache reads/writes remain parseable; transient Windows sharing failures recover within a finite bound and persistent failures propagate. Path-like queries cannot escape roots. | FR-004, FR-009, FR-017 |
| AT-08 | Fail during the second MCP start after partial allocation. Close every acquired/partial resource, record FAILED and leave another run's resources usable. | FR-002, FR-010, FR-011, FR-016 |
| AT-09 | Cancel during invocation/cleanup. Drain/cancel owned work, close resources, record CANCELLED and propagate cancellation. Cleanup failures/deadlines do not skip remaining callbacks. | FR-010, FR-011, FR-016 |
| AT-10 | Model returns but root report is absent, cleanup fails, or report publication fails. Also make an owned child agent fail through a real SDK tool boundary, then let the parent emit a valid final report. Record FAILED in all cases; no successful artifact receipt exists. | FR-010, FR-012 |
| AT-11 | After SUCCEEDED, reject late new writes and re-execution. Verify artifact hashes; inspection trusts database over stale manifest. | FR-010, FR-012 |
| AT-12 | Kill a worker after file export but before success commit. SQLite remains inspectable and run is nonterminal/unknown; files do not imply success or trigger resume. | FR-010, FR-012; NFR-005 |
| AT-13 | Plant legacy sentinel files. Supported runs never consult or mutate them. Standalone examples create fresh runs. | FR-013, FR-014 |
| AT-14 | Invoke every A2A server factory, distributed constructor and manual client. Reject before file writes, network calls or agent construction. | FR-013 |
| AT-15 | Reject invalid ID, traversal, absolute-path injection and escaping pre-existing symlink/junction. Accept valid roots containing spaces/Unicode. | FR-017 |
| AT-16 | Inject sentinel credentials and secret-bearing URLs into runtime config/errors. No secret reaches manifests/structured diagnostics; allowed provenance remains. Intended clients still receive their credentials. | FR-015, FR-018 |
| AT-17 | Invalid config fails before initialization. Runtime failure reaches caller with identity; batch exit is nonzero when any item fails. | FR-002, FR-016 |
| AT-18 | Concurrent calls on one agent instance serialize model/session activity; different agents/runs can progress independently. | FR-007 |
| AT-19 | Hold a write transaction past configured timeout. Second writer receives StateStoreUnavailable; no indefinite wait or dropped report. | FR-005; NFR-003 |
| AT-20 | Inspect auxiliary persistence paths during adapter startup. Every analysis-bearing store is run-scoped; unused MCP/direct demos validate context or fail before side effects. | FR-004, FR-008, FR-009, FR-013; NFR-004 |
| AT-21 | Exercise the shared lifecycle with every AGENT_SPECS entry and the injected store. Preserve validation/defaults/refresh, extraction and both aliases; failed/incomplete results never publish or store memory. | FR-019, FR-021 |
| AT-22 | Interleave research and risk debates across two runs. Reject a foreign/stale RoundContext before prompt rendering or memory lookup. Each participant sees only its own run's identical prior-round snapshot. | FR-003, FR-020 |
| AT-23 | Publish quorum rounds under concurrent readers/writers. Readers see the previous complete round or the new complete round, never partial reports/history. A failed commit or cancellation before commit stores no memory and permits no synthesis. | FR-005, FR-020, FR-021 |
| AT-24 | Begin a fresh manager invocation: clear only its peer/history/final alias keys atomically, preserve unrelated state and reject overlapping same-manager instances/processes. Tombstones and generation fencing reject late previous-debate writes. Replaying begin must not reset again. | FR-006, FR-020 |
| AT-25 | Inject participant-memory failure after a round commit. Preserve committed reports/history, prevent synthesis and propagate run failure even when the parent SDK converts the manager exception to a tool error and continues. Duplicate store-operation replay advances no round and causes no repeated external memory write. OFF still executes the full debate without Mem0 initialization. | FR-008, FR-010, FR-020, FR-021 |
| AT-26 | Run direct invocation, stream_async and public manager tools through the isolated boundary. The same-agent lock includes conversation clear and before/after hooks; phases/quorum and one synthesis remain unchanged, with no advancement from retries/tool turns. | FR-007, FR-019, FR-020 |
| AT-27 | Preserve blank-env model defaults and explicit overrides. RUN_ONLY search/get_all use Mem0 2.2.1 filters/top_k and cannot omit run/agent scope; current early distributed guards remain side-effect-free when broader A2A guards are added. | FR-003, FR-008, FR-013, FR-019 |

## Test guidance

Use unittest and TemporaryDirectory. Coordinate concurrency with barriers/IPC events, not arbitrary sleeps. Use multiprocessing spawn and top-level worker functions on Windows. Include local fake MCP subprocesses, partial-start injection, cleanup errors and a bounded cleanup timeout.

Prove no legacy reads with access spies/denylist as well as file hashes. Unchanged content alone does not prove no contamination. Test AT-15 using an actual permitted junction/symlink fixture; if the environment cannot create one, report missing coverage rather than declaring it passed.

Preserve the current 39-test suite across test_regressions.py, test_hook_contracts.py, test_debates.py, test_memory_configuration.py and test_model_configuration.py. Keep actual Strands hook/direct/stream/public-tool integration coverage. Tool turns and model retries must NOT advance rounds. Adapt storage fixtures and Mem0 scoping expectations deliberately; do not restore the pre-spec-003 counter or keep JSON-specific failure assumptions in isolated-runtime tests.

For AT-06/AT-20, fake Mem0 workers establish protocol, environment and filter behavior only. Also exercise the installed Mem0/Chroma persistence paths with offline model/embedding substitutes and verify retrieval isolation. For AT-07, use deterministic transient/persistent permission-error injection as well as concurrent filesystem traffic. For AT-25, assert the final RunRuntime outcome through a real parent tool invocation, not only that direct manager invocation raises.

## Requirement coverage

FR-001: AT-01, AT-02; FR-002: AT-08, AT-17; FR-003: AT-01, AT-03; FR-004: AT-01, AT-03, AT-07, AT-20; FR-005: AT-04, AT-05, AT-19; FR-006: AT-05; FR-007: AT-01, AT-03, AT-18; FR-008: AT-06, AT-20; FR-009: AT-03, AT-07, AT-20; FR-010: AT-08 through AT-12; FR-011: AT-08, AT-09; FR-012: AT-01, AT-10 through AT-12; FR-013: AT-13, AT-14, AT-20; FR-014: AT-02, AT-13; FR-015: AT-16; FR-016: AT-08, AT-09, AT-17; FR-017: AT-07, AT-15; FR-018: AT-16.

Additional coverage: FR-019: AT-21, AT-26, AT-27; FR-020: AT-22 through AT-26; FR-021: AT-21, AT-23, AT-25.

## Definition of done

- [x] AT-01 through AT-27 pass with recorded validation evidence.
- [x] Existing regression assertions pass.
- [x] Required pre-commit checks pass.
- [x] Supported entry-point/path audit finds no implicit legacy fallback.
- [x] Memory default and A2A restriction are documented.
- [x] No credentials or generated run artifacts are tracked.
- [x] Spec, contracts, implementation and tests agree.

Baseline validation on 2026-10-08: the existing 39 tests passed against c51be7f with the installed dependencies. This is not evidence that the proposed AT-01 through AT-27 isolation scenarios pass.

After implementation, run from repository root:

```powershell
uv run python -B -m unittest discover -s tests -v
uv run pre-commit run --all-files
```

Live providers/models are supplementary smoke tests, never substitutes for the isolation suite.
