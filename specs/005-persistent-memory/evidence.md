# Persistent memory acceptance evidence

**Validated:** 2026-10-25

The full offline unittest suite passed **127 tests in 45.049 seconds**, with no
skips. Applicable pre-commit checks passed.

The nine tests in `tests/test_long_term_memory.py` cover:

- PERSISTENT as the default and successful earlier-source provenance.
- Exclusion of other agents/tickers, same/future dates, RUN_ONLY and non-successful
  runs, plus sources finishing after target creation.
- Merging independent branches, deduplicating text and replacing obsolete ancestors.
- Rejection of corrupt snapshots and exports reaching the memory-count boundary.
- Atomic rejection of an altered memory artifact without publishing any receipts.
- Real Mem0/Chroma retrieval across successive private workers, using the existing
  deterministic embedding/inference fixture with networking denied in those workers.
  Retrieved records carry the target run's filters, vector/history paths remain
  private, and the original source snapshot stays byte-identical.

Existing tests retain explicit OFF behavior, RUN_ONLY run/agent filters, private
vendor imports, cleanup/cancellation and crash-gap status/artifact behavior. Workflow
fixtures explicitly choose OFF when memory inference is outside the test's scope.

These tests establish storage and retrieval boundaries. They do not establish live
model quality, financial accuracy or point-in-time correctness of external data.
