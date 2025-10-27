from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class SimfinFinancialsParameters(BaseModel):
    ticker: str = Field(..., description="ticker symbol")
    freq: str = Field(
        ...,
        description="reporting frequency of the company's financial history: annual/quarterly",
    )
    curr_date: str = Field(
        ..., description="current date you are trading at, yyyy-mm-dd"
    )
    
    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker cannot be empty")
        return v
    
    @field_validator('freq')
    @classmethod
    def validate_freq(cls, v: str) -> str:
        v = v.lower()
        if v not in ['annual', 'quarterly']:
            raise ValueError("freq must be 'annual' or 'quarterly'")
        return v
    
    @field_validator('curr_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("curr_date must be in yyyy-mm-dd format")
        return v
