# Reddit Data Server

This run-owned MCP server supplies bounded Reddit post samples for social sentiment.

## Tools

- `get_reddit_sentiment(ticker, start_date, end_date, max_posts=30)`: structured
  evidence from stocks, investing, finance, ValueInvesting, Daytrading and options.
  Dates are inclusive UTC dates. Results include post text, Reddit links, dates,
  subreddit and engagement observed at retrieval time. Search paginates up to 1000 posts per subreddit; samples are deduplicated,
  sorted newest first and bounded to 1..100 posts. Empty results mean insufficient
  evidence. Comments are not fetched; this is not an exhaustive archive.
- `get_reddit_news`: retained for compatibility with prior clients. The current
  NewsAnalyst does not connect to this server, and SocialMediaAnalyst exposes only
  the sentiment tool.

## Runtime and credentials

SocialMediaAnalyst starts this server over stdio with a validated run context and
private cache root. Direct startup without that context rejects before construction.
Set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and `REDDIT_USERNAME` in this server's
`.env`; the host passes it explicitly to uv. No parent environment is switched.

Use `uv run python -B -m utils.purge_reddit --apply` after research to purge stored
Reddit caches and redact both Reddit tool-result types in finished run sessions.

Historical coverage is explicit: `unavailable` means the search did not reach the
requested window; `partial` means incomplete coverage. The API is not an archive.
For abandoned runs, use `--abandoned-run <run_id>` only after confirming the owner
and its children stopped. Legacy cleanup is not supported.
