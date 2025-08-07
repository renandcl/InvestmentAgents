from mcp.server.fastmcp import FastMCP
from yfinance import Ticker
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

mcp = FastMCP("asset-data")

class AssetDataRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")

class AssetHistoryRequest(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    period: str = Field("1mo", description="Time period for historical data (e.g. '1d', '1mo', '1y')")

class AssetData(BaseModel):
    info: Dict[str, Any] = Field(..., description="Asset information data")

class AssetHistoryPoint(BaseModel):
    Date: Optional[str] = None
    Open: Optional[float] = None
    High: Optional[float] = None
    Low: Optional[float] = None
    Close: Optional[float] = None
    Volume: Optional[int] = None
    Dividends: Optional[float] = None
    Stock_Splits: Optional[float] = None

class AssetHistory(BaseModel):
    history: List[AssetHistoryPoint] = Field(..., description="Historical price data")

@mcp.tool()
async def get_asset_data(request: AssetDataRequest) -> AssetData:
    """Get asset data for a given symbol."""
    ticker = Ticker(request.symbol)
    return AssetData(info=ticker.info)

@mcp.tool()
async def get_asset_history(request: AssetHistoryRequest) -> AssetHistory:
    """Get historical data for a given asset symbol."""
    ticker = Ticker(request.symbol)
    history = ticker.history(period=request.period)
    return AssetHistory(history=history.to_dict(orient="records"))

if __name__ == "__main__":
    mcp.run(transport='stdio')
