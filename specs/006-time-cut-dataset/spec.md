# 006 - Time-cut data contract and frozen study dataset

**Prepared:** 2026-11-18
**Status:** Approved; delivered through stacked PRs 2 to 9 of the [design](../../docs/designs/time-cut-dataset.md).
**Extends:** [spec 001](../001-run-isolation/spec.md), [spec 004](../004-social-media-sentiment/spec.md) and [spec 005](../005-persistent-memory/spec.md).

## Outcome

Runs over past dates become backtest evidence for a paper that compares agent
architectures. No record whose `public_at` is after a run's cutoff reaches an agent, and
every architecture has the same frozen dataset available for a ticker and date. Content
revised after publication is out of scope and is disclosed in the paper.

The [design](../../docs/designs/time-cut-dataset.md) is normative for the data contracts,
fixed values, per-source rules and PR plan. This spec records the requirements and
acceptance criteria.

## Requirements

- TC-001: The evaluation date D is each Friday, or the last trading day before a closed
  Friday. The cutoff is midnight America/New_York at the end of the last trading day
  before D. A decision executes at D's adjusted close and exits at the adjusted close of
  the next scheduled weekly date.
- TC-002: A record reaches an agent only when its `public_at` is at or before the cutoff.
  Each source's `public_at` follows the design's record table.
- TC-003: `capture` stores raw vendor responses once. `build` is offline and repeatable,
  and writes one frozen copy per (ticker, date) under a new dataset ID.
- TC-004: Study runs read only the frozen copy, make no data vendor call and receive no
  vendor keys.
- TC-005: GDELT replaces DuckDuckGo as the general news source, with one request per
  candidate date and pool. Agent search terms match the frozen pool and never reach GDELT.
- TC-006: Tool date arguments stay in the schemas. Out-of-range dates are clamped, and the
  tool output says so.
- TC-007: A request the copy cannot fully answer is recorded as a miss with a reason, and
  the study reports miss counts per architecture.
- TC-008: All seven tickers share one continuous weekly calendar. A date is in the study
  only when every source meets its coverage rule for every ticker, every model's training
  cutoff is earlier and the exit price exists.
- TC-009: Each run records the dataset ID, dataset hash, cutoff and all model IDs.
- TC-010: Memory stays on. Each architecture has its own output root with one folder per
  ticker, and each ticker's dates run in ascending order. A date that still fails after two
  retries stops that ticker's chain, and a restart never repeats a succeeded date.
- TC-011: The author runs the Reddit purge manually after the study finishes. It covers the
  capture, the dataset and nested study runs, and new runs on a purged dataset are refused.

Out of scope: full point-in-time reconstruction, corporate actions and raw prices, the
step that computes returns from decisions, building the other architectures, publishing
the dataset, and forward collection on a schedule.

## Acceptance

| ID | Criterion | PR |
|---|---|---|
| AT-01 | Study dates are Fridays or the last trading day before a closed Friday, and requested dates are inclusive New York dates. The cutoff is midnight New York time at the end of the last trading day before D; a record exactly at the cutoff is admitted and one second later is not. | 2 |
| AT-02 | For every tool, a record public after the cutoff never appears, a timestamped record exactly at the cutoff is served, and a clamped request says so. | 7–9 |
| AT-03 | A study run makes no vendor call, and providers receive no vendor keys even when the parent has them. | 6–9 |
| AT-04 | Capture stores each (source, ticker) once from a candidate date list; build is repeatable offline under a new dataset ID and writes copies holding only admitted records, with capture and scoring files outside the dataset root. | 2 |
| AT-05 | A wrong expected hash fails before a run exists, and a changed copy file stops the run at provider start; a request the copy cannot answer, including another ticker or a start before the lookback, is logged with a reason. | 6–9 |
| AT-06 | Each run records dataset ID, dataset hash, cutoff and all model IDs, and commits a `misses.json` artifact. | 6 |
| AT-07 | Reddit output has no engagement counts or retrieval time, and a search with 200 or more posts is reported as capped. | 5, 9 |
| AT-08 | Coverage separates reachable-but-empty from unreachable, applies each source's coverage rule, including the three-of-five Reddit rule, and yields one calendar shared by all tickers. | 2–5 |
| AT-09 | The manual purge removes Reddit content from the capture, the dataset and nested study runs, and new runs on a purged dataset are refused. | 5–6 |
| AT-10 | A date that still fails after two retries stops that ticker's chain and reports it as incomplete, a restart continues without repeating a succeeded date, and an output root holding another dataset's runs is refused. | 6 |
