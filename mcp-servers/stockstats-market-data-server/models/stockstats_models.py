from pydantic import BaseModel, Field


class StockstatsIndicatorParameters(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL")
    indicator: str = Field(
        ...,
        description="Stockstats indicator name (e.g. rsi, macd, macdh, macds, boll, boll_ub, boll_lb, atr, vwma, mfi, close_50_sma, close_200_sma, close_10_ema)",
    )
    curr_date: str = Field(..., description="Current trading date YYYY-MM-DD")
    look_back_days: int = Field(
        30, description="Days to look back (default 30) for online report"
    )
