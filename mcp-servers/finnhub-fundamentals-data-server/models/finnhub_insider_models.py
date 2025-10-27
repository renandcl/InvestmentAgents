from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class InsiderSentimentParameters(BaseModel):
    ticker: str = Field(..., description="ticker symbol for the company")
    curr_date: str = Field(
        ..., description="current date of you are trading at, yyyy-mm-dd"
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker cannot be empty")
        return v

    @field_validator("curr_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("curr_date must be in yyyy-mm-dd format")
        return v


class InsiderTransactionsParameters(BaseModel):
    ticker: str = Field(..., description="ticker symbol")
    curr_date: str = Field(
        ..., description="current date you are trading at, yyyy-mm-dd"
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker cannot be empty")
        return v

    @field_validator("curr_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("curr_date must be in yyyy-mm-dd format")
        return v
