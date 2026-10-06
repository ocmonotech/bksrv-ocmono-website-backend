from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgencyPageBase(BaseModel):
    page_type: Literal["service", "project"]
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    excerpt: str | None = None
    content: str | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = None
    sort_order: int = 0
    status: Literal["draft", "published"] = "draft"
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)


class AgencyPageCreate(AgencyPageBase):
    pass


class AgencyPageUpdate(BaseModel):
    page_type: Literal["service", "project"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    excerpt: str | None = None
    content: str | None = None
    cover_image: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = None
    sort_order: int | None = None
    status: Literal["draft", "published"] | None = None
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)


class AgencyPageResponse(AgencyPageBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
