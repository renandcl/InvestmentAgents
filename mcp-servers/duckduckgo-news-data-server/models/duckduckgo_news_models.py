from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class DuckDuckGoNewsParameters(BaseModel):
    query: str = Field(
        ..., description="Query string to search for (company name or topic)"
    )
    start_date: str = Field(..., description="start date in yyyy-mm-dd format")
    end_date: str = Field(..., description="end date in yyyy-mm-dd format")
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query cannot be empty")
        return v
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("date must be in yyyy-mm-dd format")
        return v
