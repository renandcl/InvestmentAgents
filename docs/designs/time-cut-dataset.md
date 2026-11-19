# Time-cut data contract and frozen study dataset

*   **Author:** Renan Lima
*   **Status:** Approved
*   **Date:** 2026-11-16 (revised 2026-11-18 after the Stage 5 review)

--------------------------------------------------------------------------------

## Overview

InvestmentAgents will be used to produce backtest evidence for a paper that
compares agent architectures: a single agent, the current multi-agent tree, the
tree without debates, and a hybrid. Each run analyses one ticker at one past
evaluation date D and ends in a BUY, HOLD or SELL decision.

This design adds two guarantees to the data layer:

1.  **Time cut.** No record whose `public_at` (the time it became public) is after
    the run's cutoff reaches an agent. Content revised after publication is out of
    scope. The evaluation date D is a weekly Friday, or the last trading day
    before it when the market is closed that Friday. The cutoff is midnight New
    York time at the end of the last trading day before D. The decision is
    executed at D's closing price.
2.  **Same available data.** Every architecture that analyses the same ticker and
    date has the same frozen dataset available, identified by a hash.

It also estimates the study window the sources can support: 46 to 47 weekly dates
from about 2025-12-26 for the seven tickers in `main.py`, assuming capture around
2026-11-20. The start is limited by Finnhub's reported one-year history plus the
30-day insider lookback. Reddit, measured on 2026-11-18 with all three query variants,
allows dates from about 2025-12-12 under the three-of-five rule. The build step measures
the exact window.

## Background

**The system.** Given a ticker and a date, a tree of LLM agents produces a decision.
Four analysts (market, fundamentals, news, social media) write reports. Bull and bear
researchers debate them, a trader proposes a plan, risk debaters challenge it, and an
investment manager decides. The paper compares this tree with a single agent, the tree
without debates, and a hybrid. Each architecture is a separate batch with its own output
root.

**Terms.** A *source* is an outside data vendor. A *provider* is the MCP server process
that serves one source's data to agents through *tools*. The *host* is the Python process
that creates a run and starts its providers.

**Sources.** yfinance supplies daily prices, and stockstats computes technical indicators
from them. SimFin supplies financial statements from downloaded CSV files. Finnhub supplies
company news and insider data. Reddit supplies social posts. GDELT is a public index of
worldwide news; this design uses its DOC 2.0 article search. Its `seendate` is when GDELT
first saw an article, which is at or after publication.

**Memory.** Some agents store facts extracted from their own reports in earlier runs, and
later runs for the same ticker are seeded with them (spec 005). Seeds come only from earlier
dates, and those reports used data admitted at their own earlier cutoffs. Realised returns are
never written to memory.

## The Problem

Today the evaluation date reaches the data tools only as text in the agents'
prompts. The LLM chooses every tool argument (dates, lookback length, ticker,
search query), and nothing checks those arguments against the date being
analysed. Each provider also decides on its own whether day D is included:
yfinance, stockstats and DuckDuckGo exclude it, while Finnhub news, Reddit and
SimFin include it. As a result an agent can read news that was published after
the decision date, or read news about a price move its price series does not
show.

Several sources leak even when the dates are right:

*   Finnhub insider transactions are bounded by the date of the trade, not the
    date it was filed with the SEC, so trades reported after the cutoff appear.
*   Finnhub insider sentiment is a monthly figure, so the cutoff's own month
    includes later trades.
*   Reddit output includes vote and comment counts as of today, and the time of
    retrieval.
*   DuckDuckGo compares dates in the host machine's local time zone.

Two further problems prevent fair comparison between architectures:

*   **Live, per-run fetching.** Each run fetches data into its own private cache
    at the moment it runs. Two architectures analysing the same ticker and date
    can receive different news, because sources change between fetches.
*   **Sources that cannot look back.** In a live test on 2026-11-18, the one successful
    DuckDuckGo request reached 29 days back, later requests were refused, and custom date
    ranges remain untested, so it was not selected for historical extraction. Reddit search
    returned at most 250 posts in every one of 126 searches (7 tickers × 6 subreddits × 3
    query variants) on 2026-11-18, newest first. The sentiment service assumes 1,000 and reports truncation only
    at that count, so it never reports it.

Finally, the model's own training data is outside any data-layer cut. The
default model `qwen3:8b` has a training cutoff of 2025-03-31 according to third-party
model catalogs; Qwen has not confirmed it. Study dates must fall after it.

**Proposed solution in one paragraph.** A capture step stores each source's raw
responses once. An offline build step turns that capture into one frozen, hashed
copy per (ticker, date), holding only records that became public by that date's
cutoff, plus a coverage report. GDELT replaces DuckDuckGo as the general news
source, because it can be searched by past date. Study runs read only from the
frozen copy. A request the copy cannot answer returns "no data" and is recorded,
so missing evidence is measured instead of hidden.

## Goals

*   **Weekly evaluation dates.** D is each Friday, or the last trading day before
    it when that Friday has no session. Candidates are scheduled dates whose session
    closed before capture began. Sessions come from all seven tickers together, and a
    date is incomplete if tickers resolve to different values of D.
*   **One cutoff per run.** The cutoff is midnight America/New_York at the end of
    the last trading day before D, with daylight saving applied. Agents cannot
    change it. It falls before D's session so that no source needs intraday timing, at
    the cost of one trading day of news the agents do not see.
*   **Close-to-close scoring inputs.** A decision executes at D's adjusted close and
    exits at the adjusted close of the next scheduled weekly date. The build writes
    these prices to a scoring file. Every admitted record has a `public_at` earlier than
    the price paid.
*   **One admission rule.** A record reaches an agent only if the time it became
    public is at or before the cutoff. "Became public" is defined per source in
    the Technical Plan.
*   **GDELT replaces DuckDuckGo** as the general web-news source, with a pool of
    ticker articles and a shared pool of macroeconomic articles for each date.
*   **Repairable extraction.** Raw capture happens once. The per-date copies can
    be rebuilt offline from that capture if a cut rule has a bug.
*   **Frozen study dataset.** Study runs read a read-only dataset and never call
    a vendor. Study runs need no vendor keys.
*   **Recorded identity.** Each run records the dataset ID, dataset hash, cutoff
    and every model ID it used.
*   **Measured misses.** A miss is any recorded request the copy could not fully answer.
    The run records the request and the reason, and the study reports miss counts per
    architecture.
*   **Coverage report.** For every (source, ticker, date), the build records
    whether the source was reachable, how many records it returned, the earliest
    date reached, and whether the source met its coverage rule.
*   **Study window from measurement.** All seven tickers share one continuous weekly
    calendar. A date is in the study only when every source meets its coverage rule
    for every ticker, every model's training cutoff is earlier, and the exit price
    exists.
*   **Memory that follows the calendar.** Memory stays on. Each architecture gets
    its own output root with one sub-folder per ticker, and each ticker's dates run
    in ascending order. A date that still fails after two retries stops that ticker's
    chain, and the chain is reported as incomplete.
*   **Offline acceptance.** Offline tests verify that fixture records after the cutoff are
    not returned by any tool, that a study run makes no data vendor call, and that a changed
    manifest, or a changed file in the run's own copy before provider start, stops the run.

## Non-Goals

*   **Full point-in-time reconstruction.** Content revised after it became public
    is not restored to its original version. This covers edited or deleted Reddit
    posts, restated financial statements and prices adjusted for later splits or
    dividends. The paper discloses these as limitations.
*   **Corporate actions and raw prices.** They are not used in this study.
*   **Article text from GDELT.** GDELT returns headline, source domain, time and
    URL. The paper discloses that this source is headline-only.
*   **Removing what the model learned in training.** This is handled by choosing
    study dates after each model's training cutoff.
*   **Building the other architectures.** They are separate work. This design
    supplies the data they will read.
*   **Changing the financial prompts.** Only two edits are made: the news prompt's
    provider name "DuckDuckGo" becomes "GDELT", which spec 004 SM-001 already allows,
    and the social prompt's sentence about engagement counts is shortened to "Any sentiment
    ratios must come from the returned sample.", because those counts no longer exist in the
    tool output.
*   **The scoring step.** Computing returns and metrics from decisions is separate
    work. This design delivers only the scoring file it will read.
*   **Leaving a source role empty.** Every source role stays filled; GDELT replaces
    DuckDuckGo as general news.
*   **Publishing the dataset.** The dataset is not released with the paper. The
    code is the reference, and the paper may show examples.
*   **Forward collection on a schedule.** The study uses one historical capture.

## Design Decisions

Decided by the author on 2026-11-18. The Technical Plan builds on these.

*   **Storage unit: one frozen copy per (ticker, date).** Copies are built from a
    single capture of each (source, ticker).
*   **Scope: all runs are study runs.** The cutoff is enforced wherever data is
    served. There is no separate live, uncut mode.
*   **Execution at D's close.** Weekly dates use Friday's close, and the cutoff
    stays at midnight at the end of the previous trading day.
*   **GDELT uses one request per weekly date and pool.** This keeps extraction to
    about 380 requests. A live probe showed the cost: with relevance sorting, 151
    of 250 articles came from the window's first day. The paper discloses this
    uneven spread.
*   **Agent search terms are written by the LLM** and matched against the frozen pool.
    They never reach GDELT. Only the fixed capture queries do.
*   **News and social lookback is 7 days,** matching the prompts' "past week".
*   **Date arguments stay in the tool schemas.** Out-of-range arguments are clamped, and
    the tool output says so.
*   **Prices are adjusted.** One frozen, adjusted price series per ticker feeds both
    yfinance and stockstats. Scoring on adjusted closes therefore measures total
    return.
*   **`get_reddit_news` is removed.** No agent can reach it. The purge tool still
    recognises its name in old transcripts.
*   **Reddit output omits vote counts, comment counts and retrieval time,** because
    they are measured after the cutoff.
*   **The Reddit truncation defect is fixed here.** The service uses the measured limit
    of 250 posts and reports truncation correctly.
*   **Insider data follows the tool descriptions.** Transactions cover 30 days.
    Sentiment returns only the latest completed month.
*   **News, social and insider tools cap how many records they return,** with fixed,
    deterministic ordering.
*   **The author runs the Reddit purge manually** after the study finishes. Nothing in the
    pipeline triggers it.
*   **Scoring prices live outside the agent dataset** and are read only by the
    scoring step.
*   **SEC EDGAR replaces SimFin for financial statements** (decided 2026-11-19). The
    author's SimFin CSVs end in August 2024, before the study window, so no date could meet
    the 120-day rule. EDGAR's XBRL company facts are free, carry each filing's `filed` date
    and need only a contact `SEC_USER_AGENT`. EDGAR gets its own server,
    `edgar-fundamentals-data-server`, with its own `.env` and tools named for it
    (`get_edgar_balance_sheet`, `get_edgar_cashflow`, `get_edgar_income_statement`), because each
    server maps to one vendor. PR 3 adds it with live tools in the same layout as the other
    servers, switches the fundamentals analyst to it and removes the SimFin server; PR 8 makes
    the tools serve the frozen copy.

## Open Questions

*   **GDELT capture queries.** The live probe of the macro query (listed in the Detailed
    Implementation Plan) was refused by GDELT's rate limit, so PR 4 confirms the macro query
    and one ticker query with live requests.
*   **Finnhub history.** Finnhub's free plan reportedly keeps one rolling year of company news.
    Whether that limit also applies to insider data is unmeasured. The build's coverage report
    settles the first study date.
*   **Finnhub page maximums.** The maximum records per response for company news and insider
    transactions are unmeasured, so PRs 3 and 4 measure them live.
*   **SimFin freshness.** Resolved: the CSVs end in August 2024, so SEC EDGAR replaces SimFin
    (Design Decisions).

## Critical User Journeys (CUJs)

### CUJ 1: Capture and build a study dataset

*   **Given**: API keys for Finnhub and Reddit, an SEC contact `SEC_USER_AGENT`, a capture ID, a
    dataset ID, the seven tickers, a candidate date range and the latest model
    training cutoff.
*   **When**: The author runs `capture` once and then `build`.
*   **Then**: Raw responses are stored once. For every covered (ticker, date) there
    is a frozen copy holding only records public by that date's cutoff, plus a
    coverage report, a separate scoring-price file and a printed dataset hash.

### CUJ 2: Repair a cut rule

*   **Given**: A completed capture and a bug found in a `public_at` rule.
*   **When**: The author fixes the rule and runs `build` with a new dataset ID.
*   **Then**: A new dataset and hash are produced with no vendor call. The earlier
    dataset stays unchanged, so finished runs keep the evidence they recorded.

### CUJ 3: Run the study for one architecture

*   **Given**: A frozen dataset, its expected hash and an empty output root.
*   **When**: The batch runs every ticker's dates in ascending order.
*   **Then**: No provider contacts a vendor. Each run records the dataset ID, hash,
    cutoff and model IDs. Requests the copy cannot answer return "no data" and are
    listed in the run's miss log. A date that still fails after two retries stops that
    ticker's chain and marks it incomplete. After a crash, each ticker continues after its
    latest consecutive `SUCCEEDED` date, never repeats a succeeded date, and gives a failed date new
    retries.

### CUJ 4: Detect a changed dataset

*   **Given**: A frozen dataset changed after build, or a different hash from the one
    the author recorded.
*   **When**: A run is created or a provider starts.
*   **Then**: A wrong hash fails before a run exists, as an initialization error. A changed
    copy file stops the run at provider start, and the run fails with its run identity.

### CUJ 5: Remove deleted Reddit content

*   **Given**: The study has finished. Reddit's terms require deleted content to be removed
    from stored copies, so stored Reddit content is removed once research is complete.
*   **When**: The author runs the purge manually with `--apply`.
*   **Then**: All Reddit files are removed from the capture, the dataset and the study runs
    under an architecture's output root, and the author deletes the capture backup in the same
    procedure. The capture and dataset are marked purged, new runs
    on the dataset are refused, and `build` refuses the capture. Hashes recorded by finished
    runs remain as historical evidence.

## Technical Plan (Architecture)

### Data flow

```text
 CAPTURE (once, network on)          BUILD (offline, repeatable)
 --------------------------          ---------------------------
 extract_dataset capture             extract_dataset build
   market bars first -> candidates     one child per provider: raw -> records
   one child process per provider      narrow candidates to the study calendar
   (uv run --env-file ...)             for each study date D:
   raw responses, append-only            keep public_at <= cutoff, in lookback
         |                               write copy + coverage
         v                             scoring prices -> data/scoring/<id>/
 data/captures/<capture-id>/  ------>  (read by build; never served)
                                       manifest.json -> print dataset hash
                                                 |
                                                 v
                                       data/datasets/<id>/ (read-only)
                                                 |
 STUDY RUNS (no vendor calls, no keys)           |
 -------------------------------------           |
 main.py --dataset-id --dataset-hash --output-root
   RunConfig(ticker, D, dataset_id, dataset_hash)
   host verifies manifest hash, resolves copy and cutoff
   start_mcp(provider): dataset, copy, ticker and cutoff variables
         |
         v
 MCP tool (argument schemas kept)
   verify copy files, clamp, filter, admit, rank, cap
   miss -> "no data" + misses.jsonl
         |
         v
 agents
```

### Components

#### Component 1: Time rules (`runtime/providers/timecut.py`, new)

One module shared by the
build step and the MCP servers. It selects study dates, computes each cutoff,
applies the admission rule and clamps tool dates.

*   Trading days are the sessions that have a bar for any of the seven tickers.
*   Dates requested from any tool are inclusive New York calendar dates, compared
    with `public_at`. Tool descriptions say so.
*   A source field with only a date counts as public at 23:59:59 New York time.
*   A requested end, or a `curr_date`, after the cutoff is clamped to the last admitted New
    York trading date, and the tool output says so. `look_back_days` counts from the clamped
    date. A clamped window ends at the cutoff instant, so a record exactly at the cutoff is served.
    A clamp is not a miss.
*   A requested start before the copy's lookback moves up to the lookback start, and
    the tool output says so.
*   A window that lies entirely after the cutoff returns "no data" with the reason
    `after_cutoff`.

#### Component 2: Record envelope

Every frozen record has the shape
`{"id", "public_at", "source", "payload"}`. `id` is the source's stable identifier.

| Source / tool | `public_at` | Lookback in a copy |
|---|---|---|
| yfinance bars, stockstats | the bar's trading day (date-only rule) | full history |
| SEC EDGAR statements | the filing's `filed` date (date-only rule) | all published statements |
| Finnhub insider transactions | `filingDate` (date-only rule) | 30 days by `filingDate` |
| Finnhub insider sentiment | third weekday (Monday to Friday) of the following month (date-only rule), to allow for late filings | latest admitted month with a row, at most three months old |
| Finnhub company news | `datetime` epoch | 7 days |
| GDELT articles | `seendate` (UTC, 15-minute steps) | 7 days |
| Reddit posts | `created_utc` | 7 days |

#### Component 3: Services: fetch, normalise and serve

Each service module has three parts:

*   `fetch` calls the vendor and returns raw responses. Vendor clients are built
    only inside `fetch`, from keys in the capture process's environment.
*   `normalize` is a pure function from raw responses to record envelopes.
*   `serve` reads the frozen copy, applies the time rules and filters. News, social and
    insider tools sort newest first then by `id` and apply a cap; GDELT ranks by matched words
    first. Price, indicator and
    statement tools keep their chronological output and have no cap.

A small `capture.py` beside each server's `main.py` exposes `fetch` and `normalize`
to the extractor. Tool functions in `main.py` call only `serve`.

#### Component 4: GDELT news server (`mcp-servers/gdelt-news-data-server`, new)

Its tool keeps
DuckDuckGo's arguments (`query`, `start_date`, `end_date`).

*   Each candidate date gets one request per pool, covering the 7 days up to the cutoff,
    with relevance sorting and the 250-article maximum.
*   There are eight pools: one per ticker, with terms OR-combined, and one shared
    macro pool.
*   Capture requests the 7 days ending at the cutoff, for each candidate date. GDELT's end
    time overran by 24 hours in the live probe, so normalisation drops articles first seen
    after the cutoff. It also removes duplicate URLs and records the earliest and latest
    `seendate`.
*   GDELT's relevance ranking is not documented in anything checked, so it could reflect
    signals later than the cutoff. It can only affect which admitted articles are selected,
    and it can never admit a later article. The paper discloses this.
*   `serve` searches the ticker pool and the macro pool together. It splits the agent's
    search terms into lower-case words of two or more characters and removes the fixed
    stop-word list in the Detailed Implementation Plan. An article matches when its title contains one of the words
    as a whole word. A query word equal to the run's ticker or one of its pool terms
    matches every article in the ticker pool. Results rank by matched words, then
    newest, then `id`.
*   Output holds the headline, source domain, time and URL.

#### Component 5: Frozen dataset reader (`runtime/providers/dataset.py`, new)

Runs inside
provider processes. It validates the dataset variables, checks the copy's files
against the manifest at server start, returns one source's records and appends each
miss to `misses.jsonl` in the provider's run cache. Tickers are compared after upper-casing
and removing a leading `$`. The returned text for a miss is "no data available", except for
`before_lookback`.

| Miss reason | Meaning | Tool returns |
|---|---|---|
| `other_ticker` | The request names a ticker other than the run's. | no data available |
| `before_lookback` | The requested start is before the copy's lookback. | The data the copy holds, with a note |
| `after_cutoff` | The whole window lies after the cutoff. | no data available |
| `no_records` | The copy holds no record for the window. | no data available |
| `no_usable_terms` | The GDELT search terms have no usable word. | no data available |
| `no_term_overlap` | The GDELT search terms match no headline. | no data available |
| `invalid_window` | The requested start is after the requested end. | no data available |

#### Component 6: Extractor (`utils/extract_dataset.py`, new command)

*   `capture` takes a capture ID, a candidate date range and a minimum study date (the
    latest model training cutoff). It first captures market bars, derives each
    candidate's cutoff, execution date and exit date, and writes `candidates.json`,
    which the GDELT and Reddit children read.
*   `capture` starts one child process per provider through `uv run`, passing that
    provider's `.env` file where it has one. This keeps each server's `services` and
    `models` packages separate. Raw responses are written once under
    `data/captures/<capture-id>/`, and finished slices are skipped on resume.
*   `build` is offline and takes a capture ID and a new dataset ID. It refuses to
    overwrite an existing dataset or to read a purged capture. It runs each provider's
    `normalize` in a child process and narrows the candidates to one calendar shared by
    all seven tickers: the longest run of consecutive scheduled dates that are complete
    for every ticker.
*   Copies are written under hashed directory names, because raw tickers must not choose
    file paths (spec 001 FR-004). Runs find a copy only through its manifest entry, and
    an unknown (ticker, date) fails.
*   Coverage per (source, ticker, D) has `reachable`, `records`, `truncated`,
    `earliest_reached`, `latest_reached`, `required_start` and `coverage_rule_met`, plus per-day
    article counts for GDELT.
*   The scoring file has one row per (ticker, D): execution date and adjusted close, and
    exit date and adjusted close. The exit is the next scheduled weekly date.
*   `manifest.json` records every copy and scoring file hash, the capture hash, each
    date's cutoff, execution date and exit date, and the coverage summary.
*   The dataset hash is the SHA-256 of the manifest's bytes. `build` prints it and the
    dataset's total size, and the author keeps the hash outside the dataset.

`coverage_rule_met` follows one rule per source. A *saturated page* is one that returns the
vendor's maximum number of records, which PRs 3 and 4 measure live and record in Fixed values.
`fetch` splits a saturated sub-window until it is unsaturated, and coverage fails only if a
one-day window still saturates. The 120-day statement rule allows one quarterly reporting
cycle. `finance` is excluded from the Reddit count because it holds almost no ticker posts.

| Source | `coverage_rule_met` is true when |
|---|---|
| Prices | Bars exist for the last trading day before D, for D and for the exit date. |
| SEC EDGAR statements | The latest admitted 10-Q or 10-K statement was filed at most 120 days before the cutoff. |
| Finnhub insider transactions | Capture reached `required_start` (30 days) with no saturated page. |
| Finnhub insider sentiment | The response was reachable. A month with no row is reported as `no_records` and does not break the calendar. |
| Finnhub company news | Capture reached `required_start` (7 days) with no saturated page. |
| GDELT | The window's request succeeded. A truncated window stays complete, and its per-day article counts are reported. |
| Reddit | At least three of the five active subreddits (`stocks`, `investing`, `ValueInvesting`, `Daytrading`, `options`) reach `required_start` (7 days). A subreddit reaches it when each of its three searches holds an older post or returned fewer than 200 posts. `finance` is still captured and served, but does not count. |

#### Component 7: Run configuration and recording

`RunConfig` gains `dataset_id` and
`dataset_hash`. Run creation computes the manifest's hash, compares it with the
expected value, refuses a purged dataset and resolves the copy. `safe_config` records
the dataset ID, hash and cutoff, plus the memory LLM and embedding model IDs.
`server_parameters` passes the two reserved variables and removes vendor key names
(`FINNHUB_API_KEY`, `SEC_USER_AGENT` and `REDDIT_*`) from the child environment. At finish,
the run gathers each provider's `misses.jsonl` into one hashed `misses.json` artifact. All
study providers start with `env_file=False`.

#### Component 8: Reddit

Capture unions newest-first searches for the symbol, the `$` symbol and
the company name (Apple, Microsoft, Alphabet, Amazon, Meta Platforms, Tesla, Nvidia), and
removes duplicate posts by ID. Each search uses the 250-post limit, and a search counts as
truncated when it stops before the required start. Capped searches can return fewer than 250
posts, so a search with 200 or more posts counts as capped; the measured reach was the same at
thresholds of 200 and 225. Relevance and top sorting are not used,
because they rank on engagement measured after the cutoff. Company-name matches can include
unrelated posts, which the paper discloses. The tool output keeps `status` and `coverage`,
and reports truncation status in place of capture-time `scanned` counts.

#### Component 9: Purge (`utils/purge_reddit.py`)

The author runs this existing maintenance command manually after the
study finishes. It also covers Reddit files in the capture and dataset roots and discovers
study runs nested under an architecture's output root. It writes a `purged.json` marker in the
capture and dataset roots, outside the hashed files. The capture backup is outside the tool's
reach, so the author deletes it by hand in the same procedure.

#### Component 10: Batch protocol (`main.py`)

It takes the dataset ID, expected hash and an output
root, and reads study dates from the manifest. Each ticker runs in
`<output-root>/<ticker-key>/`, where the manifest assigns the key, so raw tickers do not choose
paths and one damaged run cannot stop another ticker's memory seeding. A failed date is retried
up to two times. If it still fails, that ticker's chain stops and is reported as incomplete. On
restart, each ticker continues after its latest consecutive `SUCCEEDED` date.

### What does not change

*   The agent tree, hook contracts and debate scheduling.
*   Memory rules from [spec 005](../../specs/005-persistent-memory/spec.md).

### Baseline specs this design amends

| Spec clause | What it says today | Change |
|---|---|---|
| [Spec 001](../../specs/001-run-isolation/spec.md) scope | Temporal validation is out of scope. | Points to spec 006. |
| Spec 001 FR-009 | Providers get private cache roots. | Adds the read-only dataset root. |
| Spec 001 FR-013 | Examples use the same run factory. | Examples take the dataset arguments. |
| Spec 001 FR-014 | Shared read-only datasets are the explicit exception. | Names this dataset. |
| Spec 001 FR-016 note | Batch failures are counted without stopping later items. | A study batch stops one ticker's chain after two retries; other tickers continue. |
| Spec 001 scope (resume) | Crash recovery and resume are out of scope. | A batch restart starts new runs for unfinished dates; no run is resumed. |
| Spec 001 AT-07, AT-28 | Live-cache behaviour. | Frozen-copy behaviour. |
| [Spec 004](../../specs/004-social-media-sentiment/spec.md) SM-001 | News uses Finnhub and DuckDuckGo. | Finnhub and GDELT. |
| Spec 004 SM-003 | Up to 1,000 results, with engagement metadata. | Three query variants, 250 posts, no engagement metadata. |
| Spec 004 SM-004, A2 | Samples are cached per run. | Samples come from the frozen copy. |
| Spec 004 plan step 3 | `get_reddit_news` is retained. | The tool is removed. |

## Alternatives Considered

"Rejected by author" records the author's decision. "Rejected in review" records a reviewer's
objection that the author accepted.

### Alternative A: Forward collection on a schedule

*   **Pros**: Retrieval time almost equals publication time.
*   **Cons**: The study grows by one date per week.
*   **Reason for Rejection**: Rejected by author: the paper needs evidence over past dates
    now, and a time cut is the guarantee required.

### Alternative B: Keep DuckDuckGo

*   **Pros**: No new server.
*   **Cons**: Its one-month filter returned nothing older than 29 days in the one request that
    succeeded. Custom date ranges could not be tested, because it refused further requests.
*   **Reason for Rejection**: Rejected by author: GDELT reached August 2024 in a live probe for
    Tesla on 2026-11-16. A 20-second request pace and resumable capture are planned, and PR 4
    confirms the queries live.

### Alternative C: Two coverage strata

*   **Pros**: A longer window for sources that reach further back.
*   **Cons**: Older dates would run with fewer sources.
*   **Reason for Rejection**: Rejected by author: uneven sources across dates would confound the
    comparison between early and late dates.

### Alternative D: Identical delivered output

*   **Pros**: Every architecture reads the same text.
*   **Cons**: Requires changing prompts or tool schemas.
*   **Reason for Rejection**: Rejected by author: the requirement is the same available
    dataset, proven by hash.

### Alternative E: Replay keyed by exact tool arguments

*   **Pros**: No new storage format.
*   **Cons**: Another architecture's calls miss, and today a miss fetches live.
*   **Reason for Rejection**: Rejected in review: the data available would depend on each
    architecture's call history.

### Alternative F: Clamp dates in a host wrapper only

*   **Pros**: Very small change.
*   **Cons**: Does not filter on when a record became public.
*   **Reason for Rejection**: Rejected in review: the cut must use each record's public time.

### Alternative G: Seven independent provider filters

*   **Pros**: Each provider stays self-contained.
*   **Cons**: Separate filters drift apart.
*   **Reason for Rejection**: Rejected in review: seven implementations would drift apart, while one
    shared rule costs only a small `public_at` mapping per source.

### Alternative H: Separate fetches per (ticker, date)

*   **Pros**: Each copy is built independently.
*   **Cons**: Adjacent dates could see different versions of the same data.
*   **Reason for Rejection**: Rejected in review: consistency across adjacent dates matters more than
    building each copy independently.

### Alternative I: A separate extractor package holding all vendor code

*   **Pros**: MCP servers hold no vendor code.
*   **Cons**: Moves vendor code out of seven servers at once.
*   **Reason for Rejection**: Rejected by author: each service keeps `fetch` beside `serve`,
    reached through one child process per provider.

### Alternative J: A generic replay MCP server

*   **Pros**: One reader for all sources.
*   **Cons**: Duplicates the formatting code and tool schemas.
*   **Reason for Rejection**: Rejected in review: replay belongs in the existing servers.

### Alternative K: Point `INVESTMENT_CACHE_ROOT` at the dataset

*   **Pros**: No new environment variable.
*   **Cons**: The cache path shape is fixed, and the cache is written while the dataset is
    read-only.
*   **Reason for Rejection**: Rejected in review: one extra variable is cheaper than weakening the
    cache path check.

### Alternative L: Grow the `data/download_data.py` scripts into the extractor

*   **Pros**: Reuses existing entry points.
*   **Cons**: They hardcode tickers, use today's date and hash nothing.
*   **Reason for Rejection**: Rejected in review: reworking them would cost more than a new command.

### Alternative M: Fail the run on a replay miss

*   **Pros**: No run is scored with missing evidence.
*   **Cons**: Architectures that make unusual calls would fail often.
*   **Reason for Rejection**: Rejected by author: failed runs would remove the architectures' behaviour
    from the comparison, while miss counts keep it measurable.

### Alternative N: Unadjusted prices plus corporate actions

*   **Pros**: Removes the leak from splits and dividends after the cutoff.
*   **Cons**: Adds data and adjustment work.
*   **Reason for Rejection**: Rejected by author: corporate actions and raw prices are not used
    for now, and the adjustment is disclosed.

### Alternative O: Remove date arguments from tool schemas

*   **Pros**: The LLM cannot ask for later dates.
*   **Cons**: Changes tool schemas and at least one prompt.
*   **Reason for Rejection**: Rejected by author: clamping gives the same protection without changing
    what the agents see.

### Alternative P: Keep `get_reddit_news` under the cut

*   **Pros**: Keeps the existing tool surface.
*   **Cons**: No agent can reach it, and it searches all of Reddit with a different query.
*   **Reason for Rejection**: Rejected by author: serving an unreachable tool adds work and no evidence.

### Alternative Q: Memory off for the study

*   **Pros**: Runs are independent of order.
*   **Cons**: Removes the learning across dates that several prompts rely on.
*   **Reason for Rejection**: Rejected by author: the current architecture depends on memory, and
    separate output roots keep it comparable.

### Alternative R: Recompute insider sentiment from filtered transactions

*   **Pros**: Includes the cutoff's own month.
*   **Cons**: Adds a home-made metric.
*   **Reason for Rejection**: Rejected by author: Finnhub's published figure is easier to defend than a
    home-made metric.

### Alternative S: Require all five active subreddits for Reddit coverage

*   **Pros**: Every date has the same mix of subreddits.
*   **Cons**: The window would be about 14 weekly dates.
*   **Reason for Rejection**: Rejected by author: the longer window matters more than an identical
    subreddit mix.

### Alternative T: A market-calendar dependency for trading days

*   **Pros**: Knows exchange holidays independently of price data.
*   **Cons**: A new dependency.
*   **Reason for Rejection**: Rejected by author: the frozen bars of all seven tickers already identify
    trading sessions.

### Alternative U: More GDELT requests per week

*   **Pros**: Three slices per week (about 1,130 requests) or daily slices (about 2,630) spread
    articles more evenly.
*   **Cons**: At least 6.3 or 14.6 hours of extraction.
*   **Reason for Rejection**: Rejected by author: there is not enough time.

### Alternative V: Execute at D's opening price

*   **Pros**: The trade is closer to the cutoff.
*   **Cons**: Weekly Friday dates and scoring are simpler with closing prices.
*   **Reason for Rejection**: Rejected by author: closing prices keep weekly execution and scoring simple.

## Risks & Mitigations

| Risk | Mitigation or acceptance |
|---|---|
| Capture cannot be repeated, because source reach shrinks every week. | The capture is append-only and hashed, resumes after interruption, and the author keeps one backup copy, which the manual purge procedure also deletes. |
| A purge ends new runs on the dataset. | The author runs the purge manually, only after the study finishes. |
| News and Reddit text is untrusted and reaches agents and memory. | Accepted and disclosed. Tools return text as data, and agents have no tool that acts outside the study. |
| One incomplete (source, ticker, date) splits the shared calendar. | The coverage report names the date and source, so the author can see what limited the window. |
| GDELT's ranking may reflect signals later than the cutoff. | Accepted and disclosed. Admission still uses `seendate`. |
| One GDELT request per week spreads articles unevenly across the window. | Accepted and disclosed, with per-day article counts in the coverage report. |
| Each of about 329 copies repeats the full price history. | Accepted. The build reports the dataset's total size. |

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Extraction time.** GDELT needs about 380 requests (8 pools × about 47 dates). At 20 seconds
    apart that is at least 2.1 hours; refusals add to it, and capture resumes after interruption.
*   **Reach shrinks weekly.** Reddit search and Finnhub's rolling year lose old data every week.
    The PR stack delivers capture before study runs, so extraction can start after PR 5.
*   **Study compute.** The study needs about 329 runs per architecture. The smoke run measures the time
    per run, which sets the total.
*   **Secrets.** Keys are read only by capture child processes. Study providers start without them.
*   **Reddit retention.** Stored Reddit content stays removable through the purge tool.
*   **Rollout.** Capture is usable after PR 5. Study runs start after PR 9.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Nine stacked PRs. Each PR adds the offline tests for the behaviour it changes, removes the tests
that behaviour replaces, and leaves the full test suite passing. Import `hash_file` (treating `None`
as a mismatch) and `atomic_write` from `runtime.store.artifacts`, and `canonical` from
`runtime.store.base`. `atomic_write` takes an object with a `.path()` method; follow the
`MemoryDirectory` adapter in `runtime/memory/snapshots.py`.

**Fixed values.**

*   Record caps per tool call: Finnhub news 50, GDELT news 50, `get_reddit_sentiment` its existing
    `max_posts` (at most 100), insider transactions 100.
*   GDELT stop words: a, an, and, are, as, at, be, by, for, from, in, is, it, of, on, or, that, the, to,
    was, were, will, with.
*   GDELT ticker queries: AAPL `("Apple" OR AAPL)`, MSFT `("Microsoft" OR MSFT)`, GOOGL
    `("Alphabet" OR "Google" OR GOOGL)`, AMZN `("Amazon" OR AMZN)`, META `("Meta Platforms" OR META)`,
    TSLA `("Tesla" OR TSLA)`, NVDA `("Nvidia" OR NVDA)`. Macro query: `("Federal Reserve" OR inflation OR
    "interest rates" OR recession OR tariffs OR "stock market")`. Every query adds `sourcelang:english`.
*   Reddit: `SENTIMENT_SEARCH_LIMIT = 250` is the request limit, and `SENTIMENT_CAPPED_POSTS = 200` is the
    count at which a search counts as capped.
*   Finnhub: `NEWS_PAGE_MAX` and `INSIDER_PAGE_MAX` are constants in each service, set from the live
    measurement in PRs 3 and 4. The measurement requests the largest window for AAPL. If no response
    saturates, the constant stays `None`, no window counts as saturated, and coverage records
    `page_max_unverified`.

### Data contracts

#### Commands

```text
python -m utils.extract_dataset capture --capture-id ID --start YYYY-MM-DD --end YYYY-MM-DD --min-date YYYY-MM-DD
python -m utils.extract_dataset build --capture-id ID --dataset-id ID
```

`capture` resumes when run again with the same capture ID. Both commands exit 0 on success and 1 on failure.

#### Provider child process

`utils/extract_dataset.py` holds a `CAPTURE_PROVIDERS` registry mapping each provider to its server folder and
whether it has an `.env` file. It starts with yfinance in PR 2, and PRs 3, 4 and 5 add their providers. Each
step runs:

```text
uv run [--env-file mcp-servers/<server>/.env] mcp-servers/<server>/capture.py fetch|normalize --request <file> --output <dir>
```

Exit 0 means success; any other code fails the step. `capture.py` calls two module-level functions in the
service, which never build the service class or need a run context:

*   `fetch(request: dict[str, Any], output: Path) -> None` writes raw vendor responses, one file per slice, then a
    `<slice>.done` marker. Finished slices are never rewritten, which makes the capture append-only.
*   `normalize(request: dict[str, Any], raw: Path) -> list[Record]` is pure. `capture.py` writes its result to
    `<output>/records.jsonl`.

The request file holds `{"ticker": "AAPL", "start": "2025-11-01", "end": "2026-11-13", "candidates": [...]}`.
Tests substitute fake children through a `provider_commands` argument on the extractor's functions.

#### Directory layout

```text
data/captures/<capture-id>/candidates.json
data/captures/<capture-id>/<source>/<ticker-key>/<slice>.json and <slice>.done
data/datasets/<dataset-id>/manifest.json
data/datasets/<dataset-id>/copies/<copy-key>/<source>.json
data/datasets/<dataset-id>/copies/<copy-key>/coverage.json
data/scoring/<dataset-id>/scoring.json
```

*   Source keys: `prices`, `edgar_balance`, `edgar_cashflow`, `edgar_income`, `insider_transactions`,
    `insider_sentiment`, `finnhub_news`, `gdelt_news`, `reddit_posts`.
*   The ticker key is the first 16 hex characters of SHA-256 over the ticker. The copy key is the same over
    `<ticker>|<YYYY-MM-DD>`.
*   The capture hash is SHA-256 over the sorted list of `<relative path>:<file hash>` lines.
*   `public_at` and every instant are ISO 8601 UTC, for example `2026-01-09T05:00:00Z`.
*   The dataset is read-only by convention: no code writes to it after `build`, and hashes detect changes. `build`
    sets no file attributes, so the purge can delete files on Windows.

#### File formats

```json
{"candidates.json": [{"date": "2026-01-09", "cutoff": "2026-01-09T05:00:00Z", "execution": "2026-01-09", "exit": "2026-01-16"}]}
```

```json
{"manifest.json": {"version": 1, "dataset_id": "study-1", "capture_id": "cap-1", "capture_hash": "<sha256>", "min_date": "2025-04-01",
  "tickers": {"AAPL": "<ticker-key>"},
  "dates": [{"date": "2026-01-09", "cutoff": "2026-01-09T05:00:00Z", "execution": "2026-01-09", "exit": "2026-01-16"}],
  "copies": {"AAPL|2026-01-09": {"key": "<copy-key>", "files": {"prices.json": "<sha256>"}}},
  "scoring": {"scoring.json": "<sha256>"}, "coverage_summary": {"excluded_dates": []}, "total_bytes": 0, "built_at": "2026-11-20T12:00:00Z"}}
```

```json
{"coverage.json": {"gdelt_news": {"reachable": true, "records": 212, "truncated": true, "earliest_reached": "2026-01-02", "latest_reached": "2026-01-09",
  "required_start": "2026-01-02", "coverage_rule_met": true, "per_day_articles": {"2026-01-02": 120}},
  "reddit_posts": {"subreddits": {"stocks": {"reached": true, "truncated": false}}}}}
```

```json
{"<source>.json": {"source": "prices", "records": [{"id": "2026-01-08", "public_at": "2026-01-09T04:59:59Z", "source": "prices", "payload": {"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1}}]}}
```

```json
{"scoring.json": [{"ticker": "AAPL", "date": "2026-01-09", "execution_date": "2026-01-09", "execution_close": 1.0, "exit_date": "2026-01-16", "exit_close": 1.0}]}
```

```json
{"purged.json": {"version": 1, "purged_at": "2026-12-01T12:00:00Z"}}
```

The outer key in each example names the file; the file holds the value.

#### Record identity

| Source key | `id` | Row dropped when |
|---|---|---|
| `prices` | bar date | The date or close is missing |
| `edgar_*` | `<freq>\|<Report Date>\|<Publish Date>`, where `freq` is `annual` (10-K) or `quarterly` (10-Q) | `filed` is missing or invalid |
| `insider_transactions` | `<filing id>\|<name>\|<transactionDate>\|<transactionCode>\|<share>\|<transactionPrice>` | `filingDate` is missing or invalid |
| `insider_sentiment` | `YYYY-MM` | The year or month is missing |
| `finnhub_news` | vendor article `id`, else URL | `datetime` is missing or invalid |
| `gdelt_news` | `<D>\|<URL>`, so each copy keeps only its own date's window | `seendate` is missing or invalid |
| `reddit_posts` | post ID | `created_utc` is missing |

Duplicate IDs keep the first record. Dropped rows are counted in `coverage.json` as `dropped_rows`.

#### Provider environment

| Variable | Value |
|---|---|
| `INVESTMENT_DATASET_DIR` | Absolute path of `data/datasets/<dataset-id>` |
| `INVESTMENT_DATASET_HASH` | Expected SHA-256 of `manifest.json` |
| `INVESTMENT_COPY_KEY` | The run's copy key |
| `INVESTMENT_TICKER` | The run's ticker, upper-case |
| `INVESTMENT_CUTOFF` | The cutoff in ISO 8601 UTC |

At server start the reader verifies the manifest's hash, then checks the copy's files against the manifest.
Each line of `misses.jsonl` holds `tool`, `arguments`, `reason` and `recorded_at`.

#### Tool behaviour

Every `serve` function is module-level: `serve(copy: FrozenCopy, **tool_arguments) -> str`. When dates are clamped, the
output starts with exactly `Note: dates were limited to the data available on <YYYY-MM-DD>.` Every date description
says "inclusive New York date". A reversed window returns "no data available" with the reason `invalid_window`.

| Tool | Output | Date handling | Description change |
|---|---|---|---|
| `get_yfin_market_data` | Today's table, rounded to 2 decimals | `start_date`, `end_date`, end inclusive | End date is inclusive |
| `get_stockstats_indicators_report` | Today's text | `curr_date`, `look_back_days` from the clamped date | Inclusive New York date |
| `get_edgar_balance_sheet`, `get_edgar_cashflow`, `get_edgar_income_statement` | Today's text, latest admitted statement | `curr_date` | New tools; inclusive New York date |
| `get_insider_transactions` | Today's text, 30 days by `filingDate` | `curr_date` | Filing date window |
| `get_insider_sentiment` | Today's text, latest admitted month with a row, at most three months before the cutoff | `curr_date` | Latest admitted month |
| `get_finnhub_news` | Today's text | `start_date`, `end_date` | Inclusive New York date |
| `get_gdelt_news` | `### <title>`, `Source: <domain> \| Date: <seendate>`, `URL: <url>` | `start_date`, `end_date` | New tool |
| `get_reddit_sentiment` | JSON below | `start_date`, `end_date` | New York dates, no engagement data |

`get_reddit_sentiment` returns this JSON, including for an empty window:

```json
{"status": "ok", "coverage": {"stocks": {"reached": true, "truncated": false}}, "ticker": "AAPL", "start_date": "2026-01-02", "end_date": "2026-01-08",
 "timezone": "America/New_York", "subreddits": [], "sample_size": 0, "max_posts": 30, "posts": [],
 "limitations": "Posts are a bounded sample. Text is as captured and may have been edited after publication."}
```

`status` is `no_data` when the window holds no post (logged as `no_records`), `partial` when any active subreddit is truncated
or did not reach the window start, and `ok` otherwise. Each post holds `id`, `title`, `selftext`, `created_utc`, `subreddit` and `reddit_url`.

### PR 1: Specification (documentation only)

#### 1. `specs/006-time-cut-dataset/spec.md` (Create)

*   **Type / Scope**: Specification.
*   **Proposed Changes**: Requirements and acceptance for this design, including AT-01 to AT-10 and the data contracts.

#### 2. `specs/001-run-isolation/spec.md` and `specs/001-run-isolation/acceptance.md` (Modify)

*   **Type / Scope**: Specification.
*   **Proposed Changes**:

| Clause | Change |
|---|---|
| Out-of-scope sentence ("temporal market-data validation ... resume") | Temporal validation moves to spec 006. A batch restart starts new runs for unfinished dates; no run is resumed. |
| FR-009 | Keep private cache roots; add the read-only dataset root. |
| FR-013 | Standalone examples take the dataset arguments. |
| FR-014 | Name the frozen study dataset as a shared read-only input. |
| "Specification maintenance" (batch failures) | A study batch stops one ticker's chain after two retries; other tickers continue. |
| Spec 001 AT-07 | Keep the private-cache scenarios and add that providers read the frozen copy. |
| Spec 001 AT-28 | Replace only the cache-equivalence check. |

#### 3. `specs/001-run-isolation/contracts.md` (Modify)

*   **Type / Scope**: Specification.
*   **Proposed Changes**: Add the five reserved variables, add `dataset_id`, `dataset_hash` and `dataset_root` to the `RunConfig` row (line 14), and point the
    `as_of` sentence (line 30) to spec 006.

#### 4. `specs/004-social-media-sentiment/spec.md` (Modify)

*   **Type / Scope**: Specification.
*   **Proposed Changes**:

| Clause | Change |
|---|---|
| SM-001 | Finnhub and GDELT. |
| Plan step 3 ("Retain get_reddit_news") | Remove `get_reddit_news`. |
| SM-003 | Three query variants, 250 posts per search, no engagement metadata. |
| SM-004, A2 | Samples come from the frozen copy instead of the run cache. |
| SM-007 | Unchanged: the purge still recognises the old tool name. |

#### 5. `AGENTS.md` and `CLAUDE.md` (Modify)

*   **Type / Scope**: Agent instructions.
*   **Proposed Changes**: Add a section describing spec 006's delivery: `capture` and `build`, the dataset, the reserved variables, and the PRs that change the standalone example
    and the news provider.

#### 6. `README.md` and `mcp-servers/reddit-news-data-server/README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: Add forward notes that point to spec 006, because the code still uses DuckDuckGo until PR 4 and `get_reddit_news` until PR 9.

### PR 2: Time rules, extractor and market capture

#### 7. `runtime/providers/timecut.py` (Create)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `Record` (frozen dataclass: `id: str`, `public_at: datetime`, `source: str`, `payload: dict[str, Any]`);
    `study_dates(start: date, end: date, trading_days: Sequence[date]) -> list[date]`; `cutoff_for(evaluation_date: date, trading_days: Sequence[date]) -> datetime`;
    `admit(public_at: datetime, cutoff: datetime) -> bool`; `public_at_from_date(day: date) -> datetime`;
    `clamp(start: date, end: date, cutoff: datetime, lookback_days: int | None) -> ClampResult`, where `ClampResult` holds `start`, `end`, `window_end: datetime`,
    `notes: tuple[str, ...]` and `miss_reason: str | None`.

#### 8. `utils/extract_dataset.py` (Create)

*   **Type / Scope**: Command-line tool.
*   **Proposed Changes**: `capture` fetches market bars first, writes `candidates.json`, then runs each registered provider's `fetch` and skips finished slices. `build` refuses an existing
    dataset ID or a purged capture, runs each provider's `normalize`, selects the shared calendar, writes copies, coverage and the scoring file, then writes the manifest and prints the
    dataset hash and total size.

#### 9. `mcp-servers/yfin-market-data-server/capture.py` (Create) and `mcp-servers/yfin-market-data-server/services/yfin_service.py` (Modify)

*   **Type / Scope**: MCP service.
*   **Proposed Changes**: `fetch` calls `yf.Ticker(symbol).history(period="max", auto_adjust=True)` once and stores unrounded Open, High, Low, Close and Volume. The capture child sets the
    yfinance cache under its capture directory. `normalize` emits `prices` records.

#### 10. `tests/test_time_cut.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: AT-01: weekly dates snap to the last trading day before a closed Friday; requested dates are inclusive New York dates; a record exactly at the cutoff is admitted and
    one second later is not; both daylight-saving offsets; clamping to the last admitted trading date; a start before the lookback; a reversed window; a window entirely after the cutoff returns
    `after_cutoff`.

#### 11. `tests/test_extract_dataset.py` (Create)

*   **Type / Scope**: Unit tests with fake provider children.
*   **Proposed Changes**: AT-04: one capture per source and ticker; capture resume skips finished slices; a rebuild makes no vendor call; copies hold only admitted records; scoring and capture files
    sit outside the dataset root; the manifest covers scoring files; `build` refuses an existing dataset ID and a purged capture. AT-08: the price coverage rule, reachable-but-empty versus
    unreachable, and one calendar shared by all tickers.

### PR 3: Fundamentals capture

#### 12. `mcp-servers/edgar-fundamentals-data-server/` with `pyproject.toml`, `README.md`, `main.py`, `models/`, `capture.py`, `services/edgar_service.py`, `services/statements_service.py`, `.env.example` (Create); `pyproject.toml`, `runtime/providers/capture.py`, `runtime/providers/mcp.py`, `utils/extract_dataset.py`, `agents/analysts/fundamentals_analyst/agent.py`, `CLAUDE.md`, `AGENTS.md`, `README.md` (Modify); `mcp-servers/simfin-fundamentals-data-server/` (Delete)

*   **Type / Scope**: MCP service and extractor.
*   **Proposed Changes**: `fetch` stores each ticker's EDGAR company facts once, using `SEC_USER_AGENT` from the server's `.env`. `normalize` emits one record per 10-K or 10-Q filing and
    statement, from a fixed list of US GAAP concepts. Each statement uses one span: a 10-Q income statement uses the quarter, a 10-Q cash flow statement the year to date (the only span
    10-Qs report), and a 10-K the full year. The span comes from the filing's fiscal period, every duration value in a statement shares one start, and
    a trailing-year value never replaces year to date. The server's `get_edgar_*` tools return the latest statement filed on or before `curr_date` from the same records, fetched live and cached per run until PR 8. Provider `.env` files are loaded only for `fetch`, so `build` runs offline without them. Providers may return coverage by date and source from `normalize`, which `build` merges; a date a provider does not cover counts as
    unreachable. Register the provider in `CAPTURE_PROVIDERS`.

#### 13. `mcp-servers/finnhub-fundamentals-data-server/capture.py` (Create); `mcp-servers/finnhub-fundamentals-data-server/services/insider_transactions_service.py`, `mcp-servers/finnhub-fundamentals-data-server/services/insider_sentiment_service.py`, `utils/extract_dataset.py` (Modify)

*   **Type / Scope**: MCP services and extractor.
*   **Proposed Changes**: Transactions `fetch` starts 30 days before the earliest `required_start` and uses 30-day sub-windows, halving a saturated one down to one day. Filings of trades older than
    that start are not captured, so a saturated page counts against a candidate when it lies within 30 days before that candidate's lookback. Sentiment `fetch` covers four months before the first candidate through the last, so every candidate's three-month lookback is reached. `normalize` applies the `public_at` rules. Measure `INSIDER_PAGE_MAX` live and register the provider.

#### 14. `tests/test_extract_dataset.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Normalisation cases for EDGAR and both insider sources, including each filing's own statement span, a late filing, the third-weekday rule, the 120-day rule,
    saturated splitting, one-day saturation and a provider gap that excludes a date from the calendar (AT-08).

### PR 4: News capture

#### 15. `mcp-servers/finnhub-news-data-server/capture.py` (Create); `mcp-servers/finnhub-news-data-server/services/finnhub_news_service.py`, `utils/extract_dataset.py` (Modify)

*   **Type / Scope**: MCP service and extractor.
*   **Proposed Changes**: `fetch` uses 30-day sub-windows, halving a saturated one down to one day; `normalize` emits one record per article. Measure `NEWS_PAGE_MAX` live and register the provider.

#### 16. `mcp-servers/gdelt-news-data-server/` with `pyproject.toml`, `README.md`, `__init__.py`, `main.py`, `models/`, `capture.py`, `services/__init__.py`, `services/gdelt_news_service.py` (Create); `utils/extract_dataset.py`, `runtime/providers/mcp.py`, `agents/analysts/news_analyst/agent.py`, `agents/analysts/news_analyst/prompt.txt`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `tests/test_provider_isolation.py`, `tests/test_social_sentiment.py` (Modify); `mcp-servers/duckduckgo-news-data-server/` (Delete)

*   **Type / Scope**: New workspace package and extractor.
*   **Proposed Changes**: The package follows the other servers' layout and uses the standard library `urllib`. Its `get_gdelt_news(query, start_date, end_date)` tool searches GDELT live for the inclusive New York dates, 5 seconds after the previous request with two retries, caches the response per run and lists up to 50 unique URLs, newest first. `PROVIDERS` and the news analyst use GDELT in place of DuckDuckGo, the news prompt names GDELT, and the DuckDuckGo server is removed. `fetch` requests
    `https://api.gdeltproject.org/api/v2/doc/doc?query=<query> sourcelang:english&mode=artlist&format=json&maxrecords=250&sort=hybridrel&startdatetime=<YYYYMMDDHHMMSS>&enddatetime=<YYYYMMDDHHMMSS>` once per pool and
    candidate date, 20 seconds apart, with a 60-second timeout and five attempts waiting 30, 60, 120 and 240 seconds. Exhausted retries leave that window unfinished, so coverage reports
    `reachable: false` and a resumed capture retries it. The macro pool is stored once under `gdelt_news/macro/` and shared by every ticker. `normalize` reads each candidate's
    cutoff from the request, applies the `seendate` cut, removes duplicate URLs, sets `pool` to `ticker` or `macro` (a URL in both stays `ticker`) and marks a window truncated at 250 articles. A copy uses only date D's window.
    The live check passes when the macro query and one ticker query each return at least one article.

#### 17. `pyproject.toml` and `uv.lock` (Modify)

*   **Type / Scope**: Build configuration.
*   **Proposed Changes**: Add the GDELT workspace member.

#### 18. `tests/test_extract_dataset.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Normalisation cases for Finnhub news and GDELT, including an article first seen after the cutoff, a truncated GDELT window that still meets its coverage rule, and exhausted retries (AT-08).

### PR 5: Reddit capture and purge

#### 19. `mcp-servers/reddit-news-data-server/capture.py` (Create); `mcp-servers/reddit-news-data-server/services/reddit_news_service.py`, `utils/extract_dataset.py` (Modify)

*   **Type / Scope**: MCP service and extractor.
*   **Proposed Changes**: Set `SENTIMENT_SEARCH_LIMIT = 250` and add `SENTIMENT_CAPPED_POSTS = 200`. `fetch` runs the three query variants per subreddit; `normalize` emits posts without `score`, `num_comments` or retrieval time.
    Subreddit reach is written to each copy's `coverage.json`. Register the provider.

#### 20. `utils/purge_reddit.py` (Modify)

*   **Type / Scope**: Maintenance command.
*   **Proposed Changes**: Add `--capture-root`, `--dataset-root` and `--study-root`, and matching `purge()` parameters. The purge deletes `reddit_posts` folders in captures and `reddit_posts.json` in copies. It finds nested study runs through the
    `ticker_key.json` marker that `main.py` writes in each ticker folder, so an unmarked folder is still reported as a skipped run. `--apply` writes `purged.json`; a dry run writes nothing.

#### 21. `tests/test_extract_dataset.py`, `tests/test_purge_reddit.py`, `tests/test_social_sentiment.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: AT-07 (normalised posts hold no engagement fields; 199 posts is not capped and 200 is), AT-08 (the three-of-five rule) and AT-09 (the purge removes Reddit files from the capture, the dataset and nested study runs, and marks the
    capture and dataset). Update the `"limit": 1000` assertion in `test_social_sentiment.py` to 250.

### PR 6: Dataset reader and host wiring

#### 22. `runtime/providers/dataset.py` (Create)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `DatasetMismatch(ContractError)`. `DatasetBinding` (frozen dataclass: `dataset_id`, `dataset_hash`, `dataset_dir: Path`, `copy_key`, `ticker`, `cutoff: datetime`). `resolve_copy(config: RunConfig) -> DatasetBinding` verifies the manifest hash,
    refuses a dataset with `purged.json` and fails on an unknown (ticker, date). `DatasetContext` (the same fields, read from the provider environment). `FrozenCopy.open(context) -> FrozenCopy`; `records(source: str) -> list[Record]`;
    `miss(tool: str, arguments: Mapping[str, Any], reason: str) -> str`.

#### 23. `runtime/core/context.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: Append `dataset_id: str = ""`, `dataset_hash: str = ""` and `dataset_root: Path = REPO_ROOT / "data" / "datasets"` to `RunConfig`; `__post_init__` raises `InvalidRunConfig` when either value is empty. Add the constants
    `MEMORY_LLM_MODEL` and `MEMORY_EMBEDDING_MODEL`.

#### 24. `runtime/memory/client.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: Read the two model IDs from the new constants.

#### 25. `runtime/execution/lifecycle.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `create_run` calls `resolve_copy` before allocating storage (spec 001 FR-002), passes the binding to `store.initialize` and sets `runtime.dataset`. After `resources.close()` and before `commit_success`, `execute` merges each provider's
    `misses.jsonl` into `misses.json`.

#### 26. `runtime/store/base.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `initialize(config, provenance, dataset: DatasetBinding)` records `dataset_id`, `dataset_hash`, `cutoff` and the memory model IDs in `safe_config`. `commit_success` adds the kind `misses` with path `misses.json`, whose content is
    `{"version": 1, "misses": []}` when there are none.

#### 27. `runtime/providers/mcp.py` (Modify)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `server_parameters` passes the five reserved variables from `runtime.dataset`, rejects a provider `.env` that sets them, and removes `FINNHUB_API_KEY`, `SEC_USER_AGENT` and `REDDIT_*` from the child environment.

#### 28. `runtime/execution/examples.py` (Modify)

*   **Type / Scope**: Entry point.
*   **Proposed Changes**: Add `--dataset-id` and `--dataset-hash`.

#### 29. `main.py` (Modify)

*   **Type / Scope**: Batch entry point.
*   **Proposed Changes**: `main(argv: Sequence[str] | None = None) -> int` takes `--dataset-id`, `--dataset-hash` and `--output-root`, verifies the manifest hash, and reads tickers and study dates from the manifest. It refuses an output root holding runs of another dataset ID or hash. Each ticker runs in
    `<output-root>/<ticker-key>/`, which holds a `ticker_key.json` marker. A date that raises `RunExecutionError` is retried up to two times, then the ticker stops and is reported as incomplete. On restart, the scan reads each run's recorded dataset fields and status and continues after the latest consecutive
    `SUCCEEDED` date. A run left in a non-terminal state counts as failed. The exit code is 0 only when every chain is complete, and 1 otherwise.

#### 30. `tests/isolation_helpers.py`, `tests/test_run_store.py`, `tests/test_run_lifecycle.py`, `tests/test_run_integration.py`, `tests/test_long_term_memory.py`, `tests/test_model_configuration.py`, `tests/test_pr_review.py`, `tests/test_provider_isolation.py` (Modify)

*   **Type / Scope**: Unit tests and helpers.
*   **Proposed Changes**: One shared fixture writes a minimal frozen dataset and builds a `DatasetBinding`, and every `RunConfig` uses it. AT-05 (a changed file or a wrong expected hash fails; a miss is logged with its reason), AT-06 (recorded fields and `misses.json`), AT-09 (a new run on a purged
    dataset is refused) and AT-10 (a repeatedly failing date stops that ticker's chain, a restart continues without repeating a succeeded date, and another dataset's output root is refused). Rewrite `test_batch_counts_initialization_failures_and_continues` for the new batch rule, update the
    `main.main` call in `tests/test_run_integration.py:773-780`, and change `test_child_environment_preserves_parent_and_env_file_credentials` to assert that vendor keys set in the parent are removed.

### PR 7: Market serving

#### 31. `mcp-servers/yfin-market-data-server/main.py`, `mcp-servers/yfin-market-data-server/services/yfin_service.py`, `mcp-servers/stockstats-market-data-server/main.py`, `mcp-servers/stockstats-market-data-server/services/stockstats_service.py`, `mcp-servers/stockstats-market-data-server/services/stockstats_utils.py` (Modify); `runtime/providers/cache.py` (Modify)

*   **Type / Scope**: MCP servers.
*   **Proposed Changes**: Tools call `serve` over the frozen `prices` records as the tool table states. stockstats computes indicators from those unrounded bars. Delete `configure_yfinance` from `runtime/providers/cache.py`.

#### 32. `tests/test_time_cut_sources.py` (Create) and `tests/test_provider_isolation.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: One table-driven test with at least one row per tool. Each row plants records around the cutoff, requests an end date years later, and checks that later records are excluded and the clamp note is present (AT-02). Timestamped sources also test a record exactly at the cutoff. Date-only sources test the last admitted date against the next date.
    Single-result tools assert that the latest admitted record wins. Tools with a ticker argument also request another ticker (AT-05). Each `curr_date` tool has a row with `curr_date = D`. Vendor clients are patched to raise, and servers start with no keys (AT-03). This PR adds the market rows, a tool-level `no_records` case and an `after_cutoff` case, and removes
    `test_yfinance_cookie_timezone_and_isin_roots_are_private` and `test_stockstats_both_paths_use_private_atomic_csv`.

### PR 8: Fundamentals serving

#### 33. `mcp-servers/edgar-fundamentals-data-server/main.py`, `mcp-servers/edgar-fundamentals-data-server/services/statements_service.py`, `mcp-servers/finnhub-fundamentals-data-server/main.py`, `mcp-servers/finnhub-fundamentals-data-server/services/insider_transactions_service.py`, `mcp-servers/finnhub-fundamentals-data-server/services/insider_sentiment_service.py` (Modify)

*   **Type / Scope**: MCP servers.
*   **Proposed Changes**: Tools call `serve` as the tool table states, and the two insider tool descriptions are updated. The EDGAR server's three tools serve the `edgar_*` records instead of fetching live.


#### 34. `agents/analysts/fundamentals_analyst/agent.py` (Modify)

*   **Type / Scope**: Agent.
*   **Proposed Changes**: Start the EDGAR and Finnhub fundamentals providers with `env_file=False`.

#### 35. `tests/test_time_cut_sources.py`, `tests/test_provider_isolation.py`, `tests/test_pr_review.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Add rows for the three statement tools and both insider tools (AT-02, AT-03, AT-05). Remove the insider case of `test_finnhub_and_duckduckgo_fresh_then_cached_do_not_share_runs` and the insider live-fetch cases at `tests/test_pr_review.py:100-136`.

### PR 9: News and Reddit serving

#### 36. `mcp-servers/finnhub-news-data-server/main.py`, `mcp-servers/finnhub-news-data-server/services/finnhub_news_service.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: The tool calls `serve`: 7-day window, newest first, cap 50.

#### 37. `mcp-servers/gdelt-news-data-server/main.py`, `mcp-servers/gdelt-news-data-server/services/gdelt_news_service.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: `get_gdelt_news` serves the frozen copy instead of searching live. Search terms are tokenised with `[a-z0-9]+(?:[&.'-][a-z0-9]+)*` after lower-casing, then stop words are removed. Pool terms per ticker are the lower-cased words of its capture query, so "Meta Platforms" gives `meta` and `platforms`. The score is the count of distinct
    matched words, plus 1 when a search word is a pool term and the article is in the ticker pool. For example, the search "Tesla recall" on the headline "Tesla issues recall" scores 3. Results rank by score, then newest, then `id`.

#### 38. `mcp-servers/reddit-news-data-server/main.py`, `mcp-servers/reddit-news-data-server/services/reddit_news_service.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: `get_reddit_sentiment` calls `serve` and returns the JSON in Data contracts. Remove the `get_reddit_news` tool and delete `RedditNewsService.get_news`.

#### 39. `agents/analysts/news_analyst/agent.py`, `agents/analysts/social_media/agent.py`, `agents/analysts/social_media/prompt.txt` (Modify)

*   **Type / Scope**: Agents.
*   **Proposed Changes**: Set `env_file=False` for the Finnhub news and Reddit providers. In the social prompt, replace the sentence "Engagement counts are observed at retrieval time, and any sentiment ratios must come from the returned sample."
    with exactly "Any sentiment ratios must come from the returned sample."

#### 40. `mcp-servers/reddit-news-data-server/README.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: Replace the forward notes from PR 1 and the
    Reddit README's `get_reddit_news` description, dates, engagement, post limit and runtime key text.

#### 41. `tests/test_time_cut_sources.py`, `tests/test_provider_isolation.py`, `tests/test_social_sentiment.py`, `tests/test_regressions.py` (Modify)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Add rows for Finnhub news, GDELT and Reddit sentiment (AT-02, AT-03). These three tools also request a start before the lookback (AT-05). Add GDELT match, `no_usable_terms` and `no_term_overlap` cases. Remove the rest of
    `test_finnhub_and_gdelt_fresh_then_cached_do_not_share_runs` and `RedditTests`. Update `test_news_and_sentiment_have_disjoint_providers_and_tools` to expect `env_file=False`, and rewrite the sentiment tests to use a frozen copy. Check that output has no engagement fields (AT-07).

### Acceptance criteria (spec 006)

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

### Verification Plan

*   **Build**: `uv sync --all-packages`.
*   **Unit Tests**: `uv run python -B -m unittest discover -s tests -v`; all offline.
*   **Static Analysis & Linting**: `uv run pre-commit run --all-files`.
*   **Size check**: `git diff --shortstat` per PR before opening it.
*   **Manual capture (once, in WSL, where the author's keys and environment live)**: run `capture` and `build` for the seven tickers. It passes when `build` exits 0, prints the dataset hash and lists at least one continuous run of covered dates; record the covered dates and truncated GDELT windows.
*   **Manual study smoke run**: run one ticker over two consecutive study dates with memory on, against the frozen dataset. Set `HTTP_PROXY` and `HTTPS_PROXY` to an unused local port and `NO_PROXY=localhost,127.0.0.1`, which blocks data vendors and keeps the local model reachable. It passes when both runs reach `SUCCEEDED` and the second run's
    `memory/<agent>/seed.json` lists the first run as a source. Record the time per run.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
