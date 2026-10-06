from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReviewSubmission(BaseModel):
    author_name: str = Field(min_length=2, max_length=120)
    author_role: str | None = Field(default=None, max_length=120)
    clinic_name: str | None = Field(default=None, max_length=180)
    rating: int = Field(ge=1, le=5)
    review_text: str = Field(min_length=10, max_length=3000)
    consent_given: bool


class ReviewStatusUpdate(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class ReviewResponse(BaseModel):
    id: int
    source: Literal["testimonial", "google"]
    author_name: str
    author_role: str | None
    clinic_name: str | None
    avatar_url: str | None
    rating: int
    review_text: str
    review_url: str | None
    consent_given: bool
    status: Literal["pending", "approved", "rejected"]
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
