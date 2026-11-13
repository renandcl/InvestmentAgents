# Persistent memory acceptance evidence

**Validated:** 2026-10-25; PM-007/PM-008 revalidated 2026-11-06

The full offline unittest suite passed **129 tests in 22.2 seconds** on Linux, with
one Windows-only skip (`test_cache_permission_recovery_and_finite_exhaustion`).
Pre-commit checks passed.

The eleven tests in `tests/test_long_term_memory.py` cover:

- PERSISTENT as the default and successful earlier-source provenance.
- Exclusion of other agents/tickers, same/future dates, RUN_ONLY and non-successful
  runs, plus sources finishing after target creation.
- Merging independent branches, deduplicating text and replacing obsolete ancestors.
- Rejection of corrupt snapshots and exports reaching the memory-count boundary.
- Seeds limited to the 365-day lookback window (A10).
- A recent memory outranking older ones of equal similarity, with at most 10
  results (A9).
- Atomic rejection of an altered memory artifact without publishing any receipts.
- Real Mem0/Chroma retrieval across successive private workers, using the existing
  deterministic embedding/inference fixture with networking denied in those workers.
  Retrieved records carry the target run's filters, vector/history paths remain
  private, the original source snapshot stays byte-identical, and the exported
  snapshot dates inherited and new memories with their own analysis dates.

Existing tests retain explicit OFF behavior, RUN_ONLY run/agent filters, private
vendor imports, cleanup/cancellation and crash-gap status/artifact behavior. Workflow
fixtures explicitly choose OFF when memory inference is outside the test's scope.

These tests establish storage and retrieval boundaries. They do not establish live
model quality, financial accuracy or point-in-time correctness of external data.
