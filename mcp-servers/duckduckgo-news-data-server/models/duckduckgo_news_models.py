from pydantic import BaseModel, Field


class DuckDuckGoNewsParameters(BaseModel):
    query: str = Field(
        ..., description="Query string to search for (company name or topic)"
    )
    start_date: str = Field(..., description="start date in yyyy-mm-dd format")
    end_date: str = Field(..., description="end date in yyyy-mm-dd format")
