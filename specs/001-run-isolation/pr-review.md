# PR #1 review corrections

**Reviewed:** 2026-10-11

| Finding | Resolution and offline regression |
|---|---|
| 1 | RunAgent catches failures around the gate and all preparation, allocating safe attempt identity before either. test_run_integration: child_preparation_failures_stay_fatal_after_sdk_tool_error covers snapshot failure, not-running status, round validation and recursion through real SDK tool errors and a parent final report. |
| 2 | Reddit search paginates up to 1000 matches per subreddit, stopping once it passes the window. Returned coverage distinguishes unavailable historical windows and partial samples. test_social_sentiment: history_is_reached_after_the_first_newest_page; unreached_historical_window_is_unavailable_not_no_data. |
| 3 | Batch catches typed configuration/allocation/store/filesystem failures, counts them, continues later jobs and prints a summary with nonzero exit status. test_pr_review: batch_counts_initialization_failures_and_continues. |
| 4 | Exported JSON omits lifecycle status and identifies its database source; report headers identify an analysis snapshot. test_pr_review: export_never_claims_success_when_commit_fails checks FAILED with no artifact receipts after a real export. |
| 5 | Missing/null Finnhub data normalizes to an empty list; malformed payloads fail before caching. test_pr_review: finnhub_empty_responses_normalize_and_bad_responses_never_cache verifies fresh/cache equivalence. |
| 6 | Explicit report presentation order puts research/risk participants before synthesis and InvestmentManager last, using declared primary keys. test_pr_review: report_follows_workflow_with_final_decision_last. |
| 7 | RunConfig.memory_request_timeout replaces fixed 120 seconds with a configurable 600-second default, persisted in safe configuration; standalone examples expose --memory-request-timeout. test_pr_review: memory_deadline_is_configurable_and_timeout_aborts_owned_worker. Expiry still aborts that worker and is fatal under FR-021; retrying an unacknowledged FIFO operation could duplicate memory writes or misattribute its late reply. |
| 8 | --abandoned-run RUN_ID explicitly opts a confirmed-stopped run into purge without changing its status. test_purge_reddit: named_abandoned_run_can_be_purged_without_changing_status also checks other live runs remain untouched. |
| 9 | --include-legacy / --legacy-root and legacy traversal are removed. test_purge_reddit: apply_preserves_legacy_and_rerun_is_idempotent verifies unchanged legacy bytes and rejected legacy CLI flags. |
| 10 | RunStore.status reads lifecycle status without decoding config, provenance, errors or artifact records. test_pr_review: status_checks_do_not_decode_full_inspection_and_observe_terminal_state proves checks bypass inspect while respecting durable terminal status. |

The full offline suite passed **118 tests in 35.897 seconds**, with no skips.
Models/providers remain offline fixtures; no live inference or Reddit request was used.

Historical Reddit coverage remains bounded. The documented [PRAW search API](https://praw.readthedocs.io/en/stable/code_overview/models/subreddit.html#praw.models.Subreddit.search)
provides sorting, relative time filters and listing pagination; these are not a
guarantee of access to arbitrary historical windows. We filter actual returned
timestamps and disclose whether the requested window was reached, rather than
using unsupported timestamp-query assumptions or claiming complete archives.
