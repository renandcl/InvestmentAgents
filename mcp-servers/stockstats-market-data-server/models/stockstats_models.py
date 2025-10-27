from pydantic import BaseModel, Field, field_validator
from datetime import datetime


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
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("symbol cannot be empty")
        return v
    
    @field_validator('indicator')
    @classmethod
    def validate_indicator(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("indicator cannot be empty")
        return v
    
    @field_validator('curr_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("curr_date must be in YYYY-MM-DD format")
        return v
    
    @field_validator('look_back_days')
    @classmethod
    def validate_look_back_days(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("look_back_days must be positive")
        return v
