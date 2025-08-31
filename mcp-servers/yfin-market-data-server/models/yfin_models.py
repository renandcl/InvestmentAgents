from pydantic import BaseModel, Field


class YFinDataParameters(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL")
    start_date: str = Field(..., description="Start date yyyy-mm-dd")
    end_date: str = Field(..., description="End date yyyy-mm-dd")
