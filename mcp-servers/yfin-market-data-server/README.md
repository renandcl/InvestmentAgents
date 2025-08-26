# YFin Market Data MCP Server

Yahoo Finance market data MCP server providing historical OHLCV (Open, High, Low, Close, Adj Close, Volume) for a given symbol and date range.

## Tool

`get_yfin_market_data` – Parameters:
- `symbol` (str): Ticker symbol, e.g. `AAPL`, `MSFT` (case-insensitive).
- `start_date` (YYYY-MM-DD): Inclusive start date.
- `end_date` (YYYY-MM-DD): Exclusive end boundary (Yahoo Finance semantics). Provide the day after the last desired bar if you want it included.

Service defaults (not exposed as parameters): `adjust=True`, output format `markdown`. CSV output or raw (unadjusted) variants can be added later if needed.

## Output

Markdown table or CSV text preceded by a short commented header. Numeric price columns rounded to 2 decimals; Volume unaltered.

## Run (standalone)

```
uv run python main.py
```
The server runs over stdio (FastMCP). Use an MCP compatible client or the existing agent framework to connect.

## Example (Agent Integration)
Add to your agent similarly to other MCP servers:
```python
from mcp.client.sse import sse_client  # or stdio transport pattern already used
# ... existing imports ...

# inside your tool loading context
with MCPClient("yfin", command=["uv", "run", "python", "-m", "yfin-market-data-server.main"]) as yfin_client:
    tools.extend(yfin_client.list_tools())
```
(Adjust import path if packaged differently; current layout exposes `main.py` at the package root.)

## Notes
- Date validation is strict (YYYY-MM-DD) and errors will bubble as validation errors in the MCP layer if malformed.
- If no rows are returned (e.g., symbol delisted or dates out of range) a plain message is returned instead of a table.
- `end_date` is exclusive per `yfinance` API; for a single day of data supply `start_date` = day and `end_date` = next day.
- Uses live Yahoo Finance data via the `yfinance` library with a local on-disk cache (`data/market_data`).

## Future Enhancements
- Optional intraday intervals.
- Batch multi-symbol retrieval.
- Local caching layer.
- Error classification (e.g., symbol not found vs network).
