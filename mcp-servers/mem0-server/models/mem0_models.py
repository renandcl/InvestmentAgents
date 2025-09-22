from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemoryAction(str, Enum):
    ADD = "add"
    GET = "get"


class MemoryParameters(BaseModel):
    action: MemoryAction = Field(..., description="The action to perform (add/get)")
    memory: Optional[str] = Field(
        None, description="The memory content to add (if action is 'add')"
    )
