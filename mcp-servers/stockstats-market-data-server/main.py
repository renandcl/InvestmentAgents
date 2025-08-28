from mcp.server.fastmcp import FastMCP
from models import StockstatsIndicatorParameters
from services import StockstatsService

mcp = FastMCP("stockstats-market-data")
service = StockstatsService()


@mcp.tool()
def get_stockstats_indicators_report(payload: StockstatsIndicatorParameters) -> str:
    """Retrieve indicator window with a default 30-day lookback.

    Convenience wrapper mapping to get_indicator_series with online=True.
    """
    symbol = payload.symbol
    indicator = payload.indicator
    curr_date = payload.curr_date
    look_back_days = payload.look_back_days

    return service.get_stock_stats_indicators_window(
        symbol=symbol,
        indicator=indicator,
        curr_date=curr_date,
        look_back_days=look_back_days,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
