from pydantic import BaseModel, Field


class FinancialsRequest(BaseModel):
    ticker: str = Field(..., description="ticker symbol")
    freq: str = Field(
        ...,
        description="reporting frequency of the company's financial history: annual/quarterly",
    )
    curr_date: str = Field(
        ..., description="current date you are trading at, yyyy-mm-dd"
    )
