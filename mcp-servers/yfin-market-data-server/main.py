from mcp.server.fastmcp import FastMCP
from models import YFinDataParameters
from services import YFinMarketDataService

mcp = FastMCP("yfin-market-data-server", "Yahoo Finance market data provider")
service = YFinMarketDataService()


@mcp.tool()
def get_yfin_market_data(payload: YFinDataParameters) -> str:
    """Fetch historical OHLCV market data for a symbol from Yahoo Finance.

    Returns a markdown table by default or CSV when format="csv".
    Date range is inclusive of start_date and exclusive of end_date per yfinance behavior (end acts as a boundary).
    """
    symbol = payload.symbol
    start_date = payload.start_date
    end_date = payload.end_date

    return service.get_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )


if __name__ == "__main__":
    mcp.run()
