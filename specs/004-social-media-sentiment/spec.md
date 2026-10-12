# 004 - Separate news and social sentiment

**Prepared:** 2026-10-11
**Status:** Implemented and validated offline; see [acceptance evidence](evidence.md).

## Outcome

The analyst coordinator invokes fundamentals, market, news and social-media agents.
News describes sourced events; social media describes opinions and attention.
Separate tools and report inputs establish these roles without repeating source-specific
warnings throughout downstream prompts.

## Requirements

- SM-001: NewsAnalyst uses Finnhub and DuckDuckGo only. Preserve its original
  financial-analysis prompt, changing only the provider names to match available tools.
- SM-002: SocialMediaAnalyst is an ANALYSTS-group RunAgent with explicit runtime,
  private sessions and no memory. It exposes only get_reddit_sentiment and writes
  social_media_analyst_report with the atomic alias social_analyst_report,
  matching the existing risk input key.
- SM-003: Retrieve posts from stocks, investing, finance, ValueInvesting, Daytrading
  and options using the ticker, sorted by newest. Paginate each search up to 1000 results;
  deduplicate post IDs, filter UTC dates inclusively, sort the combined sample and
  return at most 30 posts by default (maximum 100). Include timestamps, Reddit links,
  subreddit and observed engagement metadata with the sampling limits.
- SM-004: Cache sentiment samples under the run's existing Reddit provider root
  using separate hashed keys. Fresh and cached responses match. Empty samples
  explicitly indicate insufficient evidence, rather than neutral sentiment.
  Track the time window reached by each bounded search. If the requested historical
  window is beyond the search cap, return unavailable/partial coverage explicitly,
  rather than claiming no historical posts exist. The Reddit API is not an archive.
- SM-005: Align the social prompt with the TradingAgents sentiment analyst's role and
  analysis/output structure: a preceding-week report with sentiment direction, score,
  confidence, recurring narratives, catalysts/risks and a Markdown evidence table.
  Adapt its three-source implementation to our available get_reddit_sentiment tool.
  Base conclusions on post bodies and disclose sample/coverage limits; unavailable
  historical coverage means insufficient evidence, not neutral sentiment. Keep these
  instructions in the social analyst rather than repeating them downstream.
- SM-006: Research, trader and risk receive separate news and sentiment report inputs.
  Preserve debate scheduling, aliases and isolation behavior. Keep existing ports;
  reserve 9913 for disabled social-media A2A entry points.
- SM-007: Existing Reddit purge support redacts both get_reddit_news and
  get_reddit_sentiment transcripts without modifying committed reports/state.

## Implementation plan

Prompt reference: [TradingAgents sentiment analyst](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/analysts/sentiment_analyst.py), reviewed 2026-10-11. Its current implementation also consumes news and StockTwits; our adaptation uses the existing Reddit tool and leaves news with NewsAnalyst.

1. Extend AGENT_SPECS and downstream prompt bindings using social_analyst_report.
2. Add the social_media agent following the current agent/hook/example/A2A conventions;
   wire its tool into AnalystCoordinator and remove Reddit from NewsAnalyst.
3. Add a dedicated structured sentiment tool to the existing Reddit MCP server.
   Retain get_reddit_news for compatibility; do not expose it to the new agent.
4. Extend cleanup/redaction recognition and repository documentation.
5. Run offline acceptance with deterministic Reddit fixtures and the real Strands tree.

## Acceptance

- A1: Both agents share runtime/model settings but have disjoint provider/tool access;
  all four analyst tools execute in the offline full-tree test.
- A2: Sentiment samples reject reversed dates, exclude future/old posts, deduplicate
  across subreddits, respect bounds and preserve provenance/cache equivalence.
- A3: Published sentiment appears in downstream prompts, scoped memory queries and
  final exports; missing data remains explicit for standalone runs. Preserve separate
  report bindings while removing repeated source-specific warnings from downstream prompts.
- A4: New server/client A2A paths reject before side effects; session, lifecycle,
  resource ownership and baseline offline acceptance remain valid.
- A5: Purge fixtures redact both Reddit tool names while retaining unrelated results.

This extends run-isolation FR-022 / AT-28 and the shared contracts in specs 002/003.
