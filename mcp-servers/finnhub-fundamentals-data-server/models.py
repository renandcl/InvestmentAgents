from pydantic import BaseModel, Field

# Pydantic models for request/response validation
class InsiderSentimentRequest(BaseModel):
    ticker: str = Field(..., description="ticker symbol for the company")
    curr_date: str = Field(..., description="current date of you are trading at, yyyy-mm-dd")

class InsiderTransactionsRequest(BaseModel):
    ticker: str = Field(..., description="ticker symbol")
    curr_date: str = Field(..., description="current date you are trading at, yyyy-mm-dd")

class FinancialStatementRequest(BaseModel):
    ticker: str = Field(..., description="ticker symbol")
    freq: str = Field(..., description="reporting frequency of the company's financial history: annual/quarterly")
    curr_date: str = Field(..., description="current date you are trading at, yyyy-mm-dd")
