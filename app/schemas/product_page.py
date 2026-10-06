from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProductPageCategory = Literal[
    "apps-tools",
    "practice-types",
    "multi-clinic",
    "portfolio-applications",
    "portfolio-websites",
    "saas-product",
]
ProductPageStatus = Literal["draft", "published"]


class ProductPageBase(BaseModel):
    category: ProductPageCategory
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content: str | None = None
    icon: str | None = Field(default=None, max_length=100)
    image: str | None = Field(default=None, max_length=500)
    link: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)
    status: ProductPageStatus = "draft"
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)
    schema_json: dict[str, Any] | None = None
    capabilities_json: list[dict[str, Any]] | None = None
    saas_meta_json: dict[str, Any] | None = None


class ProductPageCreate(ProductPageBase):
    pass


class ProductPageUpdate(BaseModel):
    category: ProductPageCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    content: str | None = None
    icon: str | None = Field(default=None, max_length=100)
    image: str | None = Field(default=None, max_length=500)
    link: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0)
    status: ProductPageStatus | None = None
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: str | None = Field(default=None, max_length=50)
    schema_json: dict[str, Any] | None = None
    capabilities_json: list[dict[str, Any]] | None = None
    saas_meta_json: dict[str, Any] | None = None


class ProductPageResponse(ProductPageBase):
    id: int
    slug: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductPageMenuItem(BaseModel):
    title: str
    description: str | None = None
    link: str
    icon: str | None = None


class ProductPageMegaMenuResponse(BaseModel):
    apps_tools: list[ProductPageMenuItem]
    practice_types: list[ProductPageMenuItem]
    multi_clinic: list[ProductPageMenuItem]
