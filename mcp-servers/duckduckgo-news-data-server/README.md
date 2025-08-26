## DuckDuckGo News Data Server

This MCP server provides DuckDuckGo News results for a query within a date range.

### Tool

#### get_duckduckgo_news
Parameters:
- query: search phrase (company name or topic)
- start_date: yyyy-mm-dd
- end_date: yyyy-mm-dd

Internal defaults (not exposed as parameters): max_results=20, region=us-en, safesearch=moderate, backend=auto, timelimit inferred from date range.

Returns markdown with articles: title, source, date, snippet, URL.

### Usage
```bash
uv run main.py
```

### Notes
- DDG API (duckduckgo-search) does not guarantee exhaustive historical coverage; we fetch a superset and filter by date.
- Results cached under `data/news_data/` to minimize repeated calls.
