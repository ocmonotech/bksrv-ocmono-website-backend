from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContentBlockResponse(BaseModel):
    id: int
    slug: str
    data: Any
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentBlockUpdate(BaseModel):
    data: Any = Field(..., description="JSON content for this block")


class ContentBlockCreate(BaseModel):
    slug: str = Field(..., max_length=100)
    data: Any
