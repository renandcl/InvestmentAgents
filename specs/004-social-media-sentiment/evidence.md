# Social sentiment acceptance evidence

**Validated:** 2026-10-11

After simplifying the prompts, **18 targeted tests passed in 2.649 seconds**:
the complete hook-contract module and the real Strands full-tree integration test.
Template bindings, distinct news/sentiment inputs, report aliases and private sessions
remain valid. Manual diff review confirms NewsAnalyst matches its pre-extension prompt
except for provider names, and downstream templates retain report inputs without the
repeated social-claims paragraphs. The social prompt follows the reference's analysis
and report structure, adapted to the available Reddit source. These offline checks
validate integration; they do not measure model-generated sentiment quality.

The offline unittest suite passed **108 tests in 34.568 seconds**, with no skips.
Models, Reddit responses and MCP providers use offline fixtures. No live-provider
or sentiment-model quality claim is made.

| Acceptance | Evidence |
|---|---|
| A1 | test_social_sentiment: news_and_sentiment_have_disjoint_providers_and_tools. test_run_integration: all_real_agents_complete_with_isolated_sessions_and_no_legacy_access executes the four analyst tools in the real Strands tree. |
| A2 | test_social_sentiment: dated_deduplicated_sample_preserves_sources_and_cache; empty_and_invalid_windows_never_imply_neutral_sentiment; mcp_sentiment_adapter_validates_dates_and_returns_structured_evidence. |
| A3 | test_hook_contracts: news_and_sentiment_remain_distinct_in_prompts_and_memory_queries. The full-tree test checks both atomic sentiment aliases, downstream prompt contents and final report/session exports. |
| A4 | Existing dynamic hook/model tests now cover fourteen agents. test_run_integration: every_a2a_entry_point_rejects_before_side_effects includes the new server/client. The unchanged isolation, debate, resource and memory acceptance remains passing. |
| A5 | test_purge_reddit: sentiment_tool_results_are_redacted_alongside_legacy_news; existing purge tests preserve unrelated data, skip live runs and remain idempotent. |

The repository pre-commit hooks cover tracked and new files. Reddit uses the same
private provider cache/resource ownership, with separate sentiment cache keys.
Existing ports are preserved and 9913 is reserved for the disabled new A2A paths.

Sentiment describes a bounded post sample rather than all investors. Search may
miss historical posts; comments are not fetched and engagement is observed at
retrieval time. Empty data remains explicit. Prompt/source routing separates
reported events and opinions; it does not establish factual or statistical accuracy
of model-generated conclusions.
