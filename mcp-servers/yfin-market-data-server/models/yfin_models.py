from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class YFinDataParameters(BaseModel):
    symbol: str = Field(..., description="Ticker symbol, e.g. AAPL")
    start_date: str = Field(..., description="Start date yyyy-mm-dd")
    end_date: str = Field(..., description="End date yyyy-mm-dd")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("symbol cannot be empty")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be in yyyy-mm-dd format")
        return v
