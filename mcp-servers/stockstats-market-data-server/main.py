from mcp.server.fastmcp import FastMCP
from models import StockstatsIndicatorParameters
from services import StockstatsService

mcp = FastMCP("stockstats-market-data")
service = StockstatsService()


@mcp.tool()
def get_stockstats_indicators_report(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Retrieve indicator window with a default 30-day lookback.
    
    Args:
        symbol: Ticker symbol, e.g. AAPL
        indicator: Stockstats indicator name (e.g. rsi, macd, macdh, macds, boll, boll_ub, boll_lb, atr, vwma, mfi, close_50_sma, close_200_sma, close_10_ema)
        curr_date: Current trading date YYYY-MM-DD
        look_back_days: Days to look back (default 30) for online report

    Convenience wrapper mapping to get_indicator_series with online=True.
    """
    try:
        params = StockstatsIndicatorParameters(
            symbol=symbol,
            indicator=indicator,
            curr_date=curr_date,
            look_back_days=look_back_days
        )
        
        return service.get_stock_stats_indicators_window(
            symbol=params.symbol,
            indicator=params.indicator,
            curr_date=params.curr_date,
            look_back_days=params.look_back_days,
        )
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
