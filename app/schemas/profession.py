from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProfessionBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content: str | None = None
    image: str | None = Field(default=None, max_length=500)
    mega_menu_column: int = Field(default=0, ge=0, le=2)
    sort_order: int = Field(default=0, ge=0)
    show_on_homepage: bool = False
    animation_delay: str | None = Field(default=None, max_length=10)
    status: Literal["draft", "published"] = "draft"
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)
    schema_json: dict[str, Any] | None = None


class ProfessionCreate(ProfessionBase):
    pass


class ProfessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content: str | None = None
    image: str | None = Field(default=None, max_length=500)
    mega_menu_column: int | None = Field(default=None, ge=0, le=2)
    sort_order: int | None = Field(default=None, ge=0)
    show_on_homepage: bool | None = None
    animation_delay: str | None = Field(default=None, max_length=10)
    status: Literal["draft", "published"] | None = None
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)
    schema_json: dict[str, Any] | None = None


class ProfessionResponse(ProfessionBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfessionMegaMenuItem(BaseModel):
    title: str
    link: str


class ProfessionMegaMenuResponse(BaseModel):
    profession_columns: list[list[ProfessionMegaMenuItem]]
    footer_links: list[ProfessionMegaMenuItem]
