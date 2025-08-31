from pydantic import BaseModel, Field


class RedditNewsParameters(BaseModel):
    ticker: str = Field(..., description="ticker symbol for the company")
    start_date: str = Field(..., description="start date in yyyy-mm-dd format")
    end_date: str = Field(..., description="end date in yyyy-mm-dd format")
