## Google News Data Server

This MCP server provides Google News articles for a given query within a date range.

### Tool

#### get_google_news
Fetch Google News articles (scraped) for a query between start_date and end_date (inclusive).

Parameters:
- query: Search query (company name or topic). Spaces will be URL-encoded.
- start_date: yyyy-mm-dd
- end_date: yyyy-mm-dd

Returns a markdown-formatted list of up to 20 articles (title, source, date, snippet, URL).

### Usage

Run the server:
```bash
uv run main.py
```

The server uses stdio transport for MCP.

### Notes
- Scraping uses randomized delays and exponential backoff (tenacity) on HTTP 429 responses.
- Results are cached under `data/news_data/` to avoid repeated scraping for the same window.
- Respect Google News terms of service; this is for experimental / personal use.
