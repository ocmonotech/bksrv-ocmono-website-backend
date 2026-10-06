from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IntegrationBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content: str | None = None
    logo: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default="General", max_length=100)
    external_url: str | None = Field(default=None, max_length=500)
    card_color: int = Field(default=1, ge=1, le=4)
    sort_order: int = Field(default=0, ge=0)
    show_in_carousel: bool = False
    status: Literal["draft", "published"] = "draft"
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)
    schema_json: dict[str, Any] | None = None


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content: str | None = None
    logo: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    external_url: str | None = Field(default=None, max_length=500)
    card_color: int | None = Field(default=None, ge=1, le=4)
    sort_order: int | None = Field(default=None, ge=0)
    show_in_carousel: bool | None = None
    status: Literal["draft", "published"] | None = None
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)
    schema_json: dict[str, Any] | None = None


class IntegrationResponse(IntegrationBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
