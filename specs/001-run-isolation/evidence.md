# Run-isolation acceptance evidence

**Audit date:** 2026-10-09
**Base revision:** c51be7f190f2ecd681290c207ac77e8a43d2f876 plus the run-isolation implementation submitted for review.

The offline suite ran 98 tests successfully on Windows, including actual Strands
invocation/stream/tool execution, spawned Python workers, stdio MCP children and
installed Mem0/Chroma persistence. Model inference and provider responses were
substituted; no live market-data or model request was used. Tests use temporary
directories. The Mem0 persistence fixture also denies socket connections.

## Scenario audit

References below name test methods (without their common `test_` prefix) in the
listed modules. The implementation sources were inspected alongside these tests.

| Scenario | Evidence |
|---|---|
| AT-01 | `test_run_lifecycle`: repeat_and_interleaved_runs_export_independent_artifacts. `test_run_integration`: all_real_agents_complete_with_isolated_sessions_and_no_legacy_access; independent_spawned_runs_isolate_state_sessions_cache_and_errors. Fresh identities, private sessions/state/reports and retained outputs. |
| AT-02 | `test_run_store`: fresh_identity_and_collision_leaves_bytes_unchanged. Exclusive allocation and preserved sentinel bytes. |
| AT-03 | `test_run_integration`: both_debates_interleave_across_runs_with_frozen_snapshots; independent_spawned_runs_isolate_state_sessions_cache_and_errors. `test_provider_isolation`: real_stdio_children_use_only_their_own_cache_and_close; child_environment_preserves_parent_and_env_file_credentials. |
| AT-04 | `test_run_store`: unrelated_thread_writes_both_survive; spawned_process_writes_both_survive; round_readers_never_observe_partial_publication_or_rollback. Barriers/events coordinate independent database connections. |
| AT-05 | `test_run_store`: stale_revision_and_changed_operation_fail_without_lost_update; missing_alias_or_foreign_key_rejected; synthesis_fenced_until_quorum_and_risk_aliases_atomic. Full-tree test verifies final trader/risk aliases. |
| AT-06 | `test_run_lifecycle`: off_memory_never_imports_or_starts_vendor; memory_workers_use_private_vendor_vector_history_and_filters; real_mem0_chroma_worker_retrieval_and_auxiliary_paths. Real backend test seeds foreign run/agent rows in the same collection, verifies filtered search/get_all and inspects actual history/vector paths. |
| AT-07 | `test_provider_isolation`: hashed_canonical_keys_and_atomic_concurrent_publication; cache_permission_recovery_and_finite_exhaustion; malformed_cache_and_path_injection_fail; real_stdio_children_use_only_their_own_cache_and_close; finnhub_and_duckduckgo_fresh_then_cached_do_not_share_runs; stockstats_both_paths_use_private_atomic_csv. Windows transient recovery and exhausted retry are both exercised. |
| AT-08 | `test_provider_isolation`: partial_second_start_fails_run_without_closing_other_run; partial_mcp_start_is_registered_before_failure. `test_run_lifecycle`: partial_construction_cleanup_reverse_and_other_run_usable. Partial second acquisition closes in reverse order, records FAILED and leaves the other run usable. |
| AT-09 | `test_run_lifecycle`: cancel_invocation_closes_owned_resources_and_propagates; cancel_during_cleanup_waits_for_owned_callback; cleanup_failure_does_not_skip_callbacks_or_claim_success; deadline_records_timeout_and_attempts_remaining_cleanup. |
| AT-10 | `test_run_lifecycle`: root_absence_and_export_failure_cannot_commit_success; cleanup_failure_does_not_skip_callbacks_or_claim_success. `test_run_integration`: child_tool_failures_remain_fatal_after_parent_final_report proves SDK-converted child exceptions cannot be hidden by a parent report. |
| AT-11 | `test_run_store`: terminal_immutable_but_exact_receipt_can_be_read; final_artifacts_required_and_hash_checked. `test_run_lifecycle`: manifest_failure_after_commit_is_only_a_warning; repeat_and_interleaved_runs_export_independent_artifacts. |
| AT-12 | `test_run_lifecycle`: kill_after_export_leaves_nonterminal_without_artifact_receipts. Terminates a real owned worker at an IPC checkpoint; database remains inspectable without success receipts. |
| AT-13 | `test_run_integration`: full-tree legacy access spies plus planted sentinel byte checks; standalone_factory_allocates_fresh_run_and_batch_returns_failure. Report demo guard tested in `test_provider_isolation`. Source inventory below covers all standalone wrappers. |
| AT-14 | `test_run_integration`: every_a2a_entry_point_rejects_before_side_effects exercises every constructor, factory, manual client and __main__. Existing distributed guards remain covered by `test_debates`. |
| AT-15 | `test_run_store`: containment_rejects_injected_components_and_real_redirect; fresh_identity_and_collision_leaves_bytes_unchanged. Actual Windows symlink/junction fixture, invalid/traversing components and spaces/Unicode roots. |
| AT-16 | `test_run_integration`: credentials_reach_model_but_not_manifest_or_database_diagnostics. `test_run_store`: safe_error_excludes_raw_exception. Runtime construction-error and SDK child-error tests also inspect manifests for injected secret text; provider env-file tests preserve credential delivery. |
| AT-17 | `test_run_store`: invalid_configuration_has_no_allocation. `test_run_integration`: standalone_factory_allocates_fresh_run_and_batch_returns_failure. Lifecycle construction/error tests assert run identity and durable status. |
| AT-18 | `test_run_integration`: one_agent_serializes_direct_stream_and_cancelled_waiter; different_agents_and_runs_progress_while_one_is_blocked; queued_manager_stream_does_not_clear_active_conversation. |
| AT-19 | `test_run_store`: busy_timeout_is_named_and_bounded holds another write transaction and verifies StateStoreUnavailable. |
| AT-20 | `test_run_lifecycle`: actual Mem0/Chroma worker covers vector, entity collection, history and vendor roots. `test_provider_isolation`: yfinance_cookie_timezone_and_isin_roots_are_private; stockstats_both_paths_use_private_atomic_csv; provider_bootstraps_and_legacy_report_demo_fail_before_initialization. Auxiliary source audit below. |
| AT-21 | `test_hook_contracts` preserves all contract/default/refresh/extraction/alias/finalization checks against the injected store. `test_run_integration` completes every AGENT_SPECS entry with real SDK hooks and isolated sessions. |
| AT-22 | `test_run_integration`: both_debates_interleave_across_runs_with_frozen_snapshots coordinates four managers at each round; foreign_round_rejected_before_memory_prompt_or_conversation_reset. Store tests also reject altered identity and stale round snapshots. |
| AT-23 | `test_run_store`: round_readers_never_observe_partial_publication_or_rollback pauses after the first uncommitted participant write and checks readers before commit/rollback. `test_debates`: failures_do_not_publish_partial_round_or_synthesize; store_failure_prevents_round_memory_and_synthesis. |
| AT-24 | `test_run_store`: begin_reset_snapshot_and_replay_are_atomic_and_scoped; generation_fencing_and_monotonic_tombstones; contribution_operation_cannot_be_reused_in_another_round. `test_run_integration`: spawned_managers_cannot_claim_same_slot. |
| AT-25 | `test_run_integration`: manager_overlap_and_memory_failure_keep_complete_round; child_tool_failures_remain_fatal_after_parent_final_report. `test_hook_contracts`: receipt_replay_never_retries_external_memory. Store receipt tests verify no repeated round advance. Full-tree OFF execution has no memory directory. |
| AT-26 | `test_debates`: public_manager_tools_bind_and_run_the_scheduler; stream_api_also_runs_the_debate; research_and_risk_complete_all_participants_before_synthesis. `test_run_integration`: queued manager gate test. `test_regressions`: tool_result_turns_and_model_retries_do_not_advance_rounds. |
| AT-27 | `test_model_configuration` retains blank and explicit model settings. `test_memory_configuration` verifies five adapters and exact filters/top_k calls. Real memory worker tests verify both run and agent retrieval scope; every A2A guard remains covered. |

## Implementation and persistence inventory

- `runtime/context.py` validates before allocation and resolves immutable run paths;
  `RunStore` checks stored identity at every transaction. No ambient current-run
  global, parent environment assignment or CWD switch routes application state.
- `runtime/agent.py` gates the whole invocation, including resets and hooks.
  The runtime retains safe owned-invocation failure attribution independently of
  Strands tool exception conversion. `AgentLifecycleHooks` and `DebateRunner`
  publish with ownership/revisions/receipts; participant output remains staged
  until quorum. Store-owned generations fence reset and synthesis.
- All thirteen agent constructors require the same explicit runtime through child
  construction; all thirteen standalone agent examples and five memory examples
  use the common bootstrap. Four distributed variants and all server/client
  entry points guard before agent/network/state initialization. Existing ports
  remain reserved.
- Seven active provider bootstraps validate child identity before importing service
  implementations. Yahoo, Stockstats (both price-cache paths), Finnhub, Reddit and
  DuckDuckGo use private hashed caches. Their constructors validate cache context
  before creating provider clients. SimFin services validate context/frequency
  and only read existing shared CSV datasets. Download utilities are explicit
  offline preparation, never called by the analysis runtime.
- Installed yfinance's `set_tz_cache_location` delegates to `set_cache_location`,
  setting timezone, cookie and ISIN stores together; the adapter permits this
  only in its run-owned provider process. Child vendor/temp environment paths are
  private. Installed Mem0 imports may create vendor configuration, so MEM0_DIR
  and telemetry settings are supplied before child import. Its history path is
  explicit; the auxiliary entity collection clones the same private Chroma path,
  confirmed by the real-backend test. Shared dependency/model files are not
  analysis state.
- Unused Google News and Mem0 MCP implementations reject initialization.
  `utils/report.py` only renders an explicit StateSnapshot and its old CLI is
  guarded. `JsonReportStore` remains an explicit-path legacy test adapter; no
  runtime/agent path constructs it. Searches found no executable global legacy
  analysis-path reference in supported agents/runtime/providers/reporting.
- `ResourceRegistry` registers before start, closes in reverse order and attempts
  all callbacks within finite budgets. Only owned client/process handles are
  stopped. Successful export requires root report, no owned invocation failure,
  successful cleanup and a database transaction containing hashes/status. A
  derived manifest failure cannot reverse committed success.

## Release gates and limits

- Requirement mapping: acceptance.md maps every FR-001..FR-021 to the scenarios
  above. NFR-001..006 are supported by the Windows/pinned-stack execution,
  offline fixtures, bounded contention/cleanup, vendor-path inventory, real
  hard-kill test and retained baseline assertions/unchanged financial prompts.
- Ruff, Black, secret detection, private-key/file/whitespace checks passed with
  tracked and untracked files included. Test-only dummy credentials have narrow
  inline annotations. The lockfile and financial prompt files are unchanged.
- README, AGENTS.md and CLAUDE.md document memory OFF/RUN_ONLY, runtime injection,
  private output locations, failure behavior and the all-A2A compatibility change.
- No generated data/reports or credentials are tracked; no commit/push or legacy
  data migration/deletion is part of this delivery.
- Verified scope is trusted in-process/local-host execution with local storage.
  No live-provider/model quality claim, temporal correctness, distributed mode,
  resume, crash takeover or exactly-once external-memory delivery is implied.
