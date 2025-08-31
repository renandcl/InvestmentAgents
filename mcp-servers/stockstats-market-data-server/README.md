# Stockstats Market Data MCP Server

Provides access to technical indicators computed via the `stockstats` library over Yahoo Finance price history.

## Tool

`get_stockstats_indicator_series`

Parameters:
- `symbol`: Ticker symbol (e.g. AAPL)
- `indicator`: One of the supported indicators.
- `curr_date`: Reference (end) date YYYY-MM-DD.
- `look_back_days`: If 0 returns only the value on `curr_date`; if >0 returns table for window.
- `online`: When True, fetches/updates price history from Yahoo Finance (15y window) and caches under `data/market_data/price_data/`.

Supported indicators include:
`close_50_sma`, `close_200_sma`, `close_10_ema`, `macd`, `macds`, `macdh`, `rsi`, `boll`, `boll_ub`, `boll_lb`, `atr`, `vwma`, `mfi`.

`get_stockstats_indicators_report_online`

Parameters:
- `symbol`, `indicator`, `curr_date`, optional `look_back_days` (default 30). Always uses live fetch (online=True) before computing the indicator window.

## Caching

Price history stored as CSV named `{SYMBOL}-YFin-data-<start>-<end>.csv` in `data/market_data/price_data`. Indicator values are computed on demand (no separate cache file).

## Run

```
uv run python main.py
```

Use an MCP-compatible client (or existing agent loader pattern) to connect and invoke the tool.

## Future Enhancements
- Batch multi-indicator retrieval in one call
- Interval / intraday support
- Indicator parameter customization (periods, std dev, etc.)
- Error taxonomy for clearer upstream handling
