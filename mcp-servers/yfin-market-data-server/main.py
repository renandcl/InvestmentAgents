from mcp.server.fastmcp import FastMCP
from models import YFinDataParameters
from services import YFinMarketDataService

mcp = FastMCP("yfin-market-data-server", "Yahoo Finance market data provider")
service = YFinMarketDataService()


@mcp.tool()
def get_yfin_market_data(symbol: str, start_date: str, end_date: str) -> str:
    """Fetch historical OHLCV market data for a symbol from Yahoo Finance.
    
    Args:
        symbol: Ticker symbol, e.g. AAPL
        start_date: Start date yyyy-mm-dd
        end_date: End date yyyy-mm-dd

    Returns a markdown table by default or CSV when format="csv".
    Date range is inclusive of start_date and exclusive of end_date per yfinance behavior (end acts as a boundary).
    """
    try:
        params = YFinDataParameters(symbol=symbol, start_date=start_date, end_date=end_date)
        
        return service.get_data(
            symbol=params.symbol,
            start_date=params.start_date,
            end_date=params.end_date,
        )
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
