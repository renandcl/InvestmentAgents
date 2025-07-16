from mcp.server.fastmcp import FastMCP
from yfinance import Ticker

mcp = FastMCP("asset-data")

@mcp.tool()
async def get_asset_data(symbol: str) -> dict:
    """Get asset data for a given symbol."""
    ticker = Ticker(symbol)
    return ticker.info

@mcp.tool()
async def get_asset_history(symbol: str, period: str = "0mo") -> dict:
    """Get historical data for a given asset symbol."""
    ticker = Ticker(symbol)
    history = ticker.history(period=period)
    return history.to_dict(orient="records")

if __name__ == "__main__":
    mcp.run(transport='stdio')
