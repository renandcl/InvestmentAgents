# Implementation tasks

**Status:** Implemented and validated offline on 2026-10-09. Task completion is backed by the test/source audit in evidence.md and the final 98-test and pre-commit results.

**Update review:** Remote master and local HEAD were verified at c51be7f. The review findings around SDK failure propagation, Windows cache contention, acceptance coverage and repository documentation are resolved in this implementation.

## Phase 1 - Runtime foundation

- [x] T001 Record c51be7f baseline/provenance and current locked dependencies; preserve all 39 tests across five modules. Reuse spec 002/003 contracts instead of reimplementing completed work. [FR-018; AT-16]
- [x] T002 Add runtime context/config, fresh UUID allocation, exclusive directory creation and path containment. [FR-001..004, FR-017; AT-01, AT-02, AT-15, AT-17]
- [x] T003 Add transactional RunStore, per-key/tombstone revisions, operation receipts and events; define the shared repository boundary needed by both hooks and debates. [FR-005, FR-006; AT-04, AT-05, AT-19]
- [x] T004 Add lifecycle, errors/results and terminal-write enforcement. Retain owned-agent failures across SDK tool-error conversion and prevent a later successful root result from clearing them. [FR-010, FR-012, FR-016; AT-10, AT-11, AT-17]

Dependencies: T002 -> T003 -> T004. Add component tests before corresponding integration.

## Phase 2 - Agent integration

- [x] T005 Thread explicit runtime dependencies through all 13 agent implementations and child construction. Resolve model settings once per run. [FR-003; AT-03, AT-17]
- [x] T006 Inject RunStore into agents/hooks/lifecycle.py and adapt shared services plus all 13 thin hook selectors. Derive ownership/aliases from AGENT_SPECS; preserve successful-finalization checks. [FR-005, FR-006, FR-019, FR-021; AT-04, AT-05, AT-21]
- [x] T007 Scope sessions and serialize the complete same-agent direct/stream/tool lifecycle, including debate conversation resets and hooks. [FR-007, FR-020; AT-01, AT-18, AT-26]

- [x] T021 Extend RoundContext and DebateRunner ownership with run/manager/invocation identity; reject foreign/stale contexts before side effects. [FR-003, FR-020; AT-22, AT-24]
- [x] T022 Implement begin_debate/commit_round/end_debate, atomic scoped reset, tombstones, quorum/history receipts and synthesis fencing. Replace runner JSON patches without weakening DebateState. [FR-005, FR-006, FR-020; AT-23, AT-24]
- [x] T023 Preserve staged participant outputs and commit-before-memory ordering in shared hooks/runner; prevent duplicate receipt side effects and retain complete data on memory failure. [FR-019, FR-021; AT-21, AT-25]

Dependencies: T004 -> T005; T005 -> T007/T021; T003/T021 -> T022; T022 -> T006; T006/T008/T022 -> T023. The complete debate store contract precedes switching the shared lifecycle.

## Phase 3 - Memory and providers

- [x] T008 Add non-null NullMemory compatible with spec.memory validation and a RUN_ONLY factory; update five adapters with explicit history_db_path and current filters/top_k API. Adapt the memory configuration test for run-scoped retrieval. [FR-008; AT-06, AT-20]
- [x] T009 Add owned-resource registry and MCP cleanup, including partial starts, cancellation, deadline and cleanup-error handling. [FR-011; AT-08, AT-09]
- [x] T010 Supply reserved child run/cache context without global mutation; preserve credentials and reject conflicts. [FR-009, FR-015; AT-03, AT-07, AT-16]
- [x] T011 Migrate active provider caches, both Stockstats paths, safe hashed keys and atomic publication. Handle transient Windows read/replace contention within finite bounds; test recovery and persistent failure. [FR-004, FR-009, FR-017; AT-07]
- [x] T012 Audit Google News, Mem0 MCP, direct demos and auxiliary library stores. Require context or guard startup; keep shared SimFin inputs read-only. [FR-004, FR-013, FR-014; AT-13, AT-20]

Dependencies: T005 -> T008/T009; T009 -> T010 -> T011; T008/T011 -> T012.

## Phase 4 - Runner and compatibility

- [x] T013 Wrap root construction/invocation in RunRuntime; propagate identity/outcome and nonzero batch failure. [FR-002, FR-010, FR-016; AT-08..10, AT-17]
- [x] T014 Render final snapshot into run-owned UTF-8 state/report exports; commit hashes/status and implement derived manifest inspection. Reuse the runtime renderer and migrate or guard the legacy utils/report.py demo. [FR-012, FR-015, FR-018; AT-10..12, AT-16]
- [x] T015 Migrate all agent/memory standalone examples to fresh-run bootstrap. [FR-013, FR-014; AT-01, AT-13]
- [x] T016 Preserve existing research/risk distributed guards; extend coverage to remaining variants, A2A server factories and manual clients. Document the added restriction on spec-003 local-participant A2A servers and retain ContractError compatibility; keep ports unchanged. [FR-013; AT-14]

Dependencies: T007..T012 and T021..T023 -> T013 -> T014/T015. T016 requires T004 and must ship with the feature.

## Phase 5 - Acceptance and documentation

- [x] T017 Execute task/thread/process isolation, revisions, cache and serialization tests. [AT-01..07, AT-18, AT-19]
- [x] T018 Execute failure/cancellation/cleanup/export/hard-kill scenarios. [AT-08..12, AT-17]
- [x] T019 Audit legacy access, paths, secrets, unsupported modes and vendor stores. [AT-13..16, AT-20]
- [x] T020 Update README and repository instructions, run regression/pre-commit checks, and record acceptance evidence. [All requirements]

- [x] T024 Implement and execute new shared-lifecycle/debate isolation scenarios, including real SDK streaming, reset generations, atomic quorum publication and post-commit memory failures. [AT-21..27]

Dependencies: T013..T016 and T021..T023 -> T017..T020/T024. T020 records the full AT-01..27 result after T024.

## Suggested change boundaries

1. Runtime contracts/store and tests.
2. Shared hook/session/memory integration and debate-aware transactional publication.
3. MCP cache/resource isolation.
4. Runner/export/entry-point migration and complete acceptance.

Intermediate code does not establish complete isolation. Avoid unrelated prompt/model changes, dependency upgrades and new financial logic.
