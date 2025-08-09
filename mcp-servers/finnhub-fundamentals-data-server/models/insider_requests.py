from pydantic import BaseModel, Field


class InsiderSentimentRequest(BaseModel):
    ticker: str = Field(..., description="ticker symbol for the company")
    curr_date: str = Field(
        ..., description="current date of you are trading at, yyyy-mm-dd"
    )


class InsiderTransactionsRequest(BaseModel):
    ticker: str = Field(..., description="ticker symbol")
    curr_date: str = Field(
        ..., description="current date you are trading at, yyyy-mm-dd"
    )
