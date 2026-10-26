# Run-isolation implementation progress

**Updated:** 2026-10-09
**Baseline:** c51be7f190f2ecd681290c207ac77e8a43d2f876
**Status:** Implemented and validated offline; prepared for pull-request review.

## Delivered

- Immutable fresh run identity, private roots and per-run SQLite with short
  transactions, report ownership/aliases, revisions, receipts and terminal checks.
- Explicit runtime integration across all thirteen agents, shared hooks and debate
  runner. Whole-invocation serialization, private sessions, frozen round snapshots,
  atomic reset/quorum publication and generation fencing preserve spec 002/003.
- Memory OFF without vendor initialization; RUN_ONLY uses owned per-agent workers
  with private vendor/vector/history/entity stores and enforced retrieval scope.
- Explicit MCP child context, private hashed provider caches, bounded Windows
  read/replace retries, read-only SimFin datasets and owned-resource cleanup.
- Root/standalone lifecycle, safe failure attribution even across SDK tool-error
  conversion, nonzero batch failure, atomic exports/hash receipts and derived
  manifests. All A2A paths reject early with reserved ports unchanged.
- Snapshot-only report rendering; legacy artifacts remain untouched. README and
  repository instructions describe new outputs, memory policy and compatibility.

## Verification

The final `.venv/Scripts/python.exe -B -m unittest discover -s tests -v` run passed
**98 tests in 38.308 seconds**, with no skips. This includes the adapted baseline
assertions, full real-SDK agent-tree execution, synchronized thread/process/debate
tests, actual stdio MCP children, real Mem0/Chroma persistence with offline inference,
failure/cancellation/deadline injection and a killed worker at the export gap.

`uv run pre-commit run --all-files` passed. The same hooks passed with new/untracked
files explicitly included. Financial prompts and uv.lock are unchanged. Generated
run data/reports are not tracked. Dummy credential fixtures use narrow inline
secret-scanner annotations.

[evidence.md](evidence.md) maps AT-01..27 to tests and inspected implementation
paths, and records the functional/nonfunctional requirement audit.

## Scope and limits

Supported: trusted in-process runs and standalone examples, including concurrent
independent runs on one local host. Memory defaults OFF. RUN_ONLY has no cross-run
learning. No live-provider/model quality claim, network-filesystem support,
distributed A2A, temporal correctness, automatic resume/takeover, retention policy
or exactly-once external-memory guarantee is included. Hard kills may leave a
nonterminal run; SQLite and artifact receipts determine success.

No data migration or legacy-data deletion was performed.
