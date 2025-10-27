from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class RedditNewsParameters(BaseModel):
    ticker: str = Field(..., description="ticker symbol for the company")
    start_date: str = Field(..., description="start date in yyyy-mm-dd format")
    end_date: str = Field(..., description="end date in yyyy-mm-dd format")
    
    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker cannot be empty")
        return v
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("date must be in yyyy-mm-dd format")
        return v
