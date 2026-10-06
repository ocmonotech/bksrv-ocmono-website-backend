from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


RobotsValue = Literal[
    "index,follow",
    "noindex,follow",
    "index,nofollow",
    "noindex,nofollow",
]


class SeoSiteSettingsUpdate(BaseModel):
    site_name: str | None = Field(default=None, max_length=255)
    title_suffix: str | None = Field(default=None, max_length=255)
    default_meta_description: str | None = None
    default_og_image: str | None = Field(default=None, max_length=500)
    twitter_handle: str | None = Field(default=None, max_length=100)
    robots_default: RobotsValue | None = None
    google_site_verification: str | None = Field(default=None, max_length=255)
    bing_site_verification: str | None = Field(default=None, max_length=255)
    organization_schema: dict[str, Any] | None = None
    sitemap_enabled: bool | None = None
    robots_extra: str | None = None
    gtm_enabled: bool | None = None
    gtm_container_id: str | None = Field(default=None, max_length=50)
    ga4_enabled: bool | None = None
    ga4_measurement_id: str | None = Field(default=None, max_length=50)
    meta_pixel_enabled: bool | None = None
    meta_pixel_id: str | None = Field(default=None, max_length=50)
    linkedin_enabled: bool | None = None
    linkedin_partner_id: str | None = Field(default=None, max_length=50)
    clarity_enabled: bool | None = None
    clarity_project_id: str | None = Field(default=None, max_length=50)
    custom_head_scripts: str | None = None
    custom_body_scripts: str | None = None


class SeoSiteSettingsResponse(BaseModel):
    id: int
    site_name: str
    title_suffix: str | None = None
    default_meta_description: str | None = None
    default_og_image: str | None = None
    twitter_handle: str | None = None
    robots_default: str
    google_site_verification: str | None = None
    bing_site_verification: str | None = None
    organization_schema: dict[str, Any] | None = None
    sitemap_enabled: bool
    robots_extra: str | None = None
    gtm_enabled: bool = False
    gtm_container_id: str | None = None
    ga4_enabled: bool = False
    ga4_measurement_id: str | None = None
    meta_pixel_enabled: bool = False
    meta_pixel_id: str | None = None
    linkedin_enabled: bool = False
    linkedin_partner_id: str | None = None
    clarity_enabled: bool = False
    clarity_project_id: str | None = None
    custom_head_scripts: str | None = None
    custom_body_scripts: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeoPageBase(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    label: str | None = Field(default=None, max_length=255)
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: RobotsValue | None = None
    schema_json: dict[str, Any] | None = None
    sitemap_include: bool = True
    sitemap_priority: str | None = Field(default="0.7", max_length=10)
    sitemap_changefreq: str | None = Field(default="weekly", max_length=20)


class SeoPageCreate(SeoPageBase):
    pass


class SeoPageUpdate(BaseModel):
    path: str | None = Field(default=None, min_length=1, max_length=500)
    label: str | None = Field(default=None, max_length=255)
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: RobotsValue | None = None
    schema_json: dict[str, Any] | None = None
    sitemap_include: bool | None = None
    sitemap_priority: str | None = Field(default=None, max_length=10)
    sitemap_changefreq: str | None = Field(default=None, max_length=20)


class SeoPageResponse(SeoPageBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeoRedirectBase(BaseModel):
    from_path: str = Field(min_length=1, max_length=500)
    to_path: str = Field(min_length=1, max_length=1000)
    status_code: Literal[301, 302, 307, 308] = 301
    is_active: bool = True
    note: str | None = Field(default=None, max_length=500)


class SeoRedirectCreate(SeoRedirectBase):
    pass


class SeoRedirectUpdate(BaseModel):
    from_path: str | None = Field(default=None, min_length=1, max_length=500)
    to_path: str | None = Field(default=None, min_length=1, max_length=1000)
    status_code: Literal[301, 302, 307, 308] | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class SeoRedirectResponse(SeoRedirectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SeoAuditItem(BaseModel):
    entity_type: str
    entity_id: int | str | None = None
    title: str
    path: str
    status: str | None = None
    issues: list[str]
    score: int


class SeoAuditResponse(BaseModel):
    summary: dict[str, int]
    items: list[SeoAuditItem]


class SeoSitemapEntry(BaseModel):
    path: str
    lastmod: datetime | None = None
    changefreq: str | None = None
    priority: float | None = None


class SeoSitemapResponse(BaseModel):
    enabled: bool
    entries: list[SeoSitemapEntry]


class SeoRobotsResponse(BaseModel):
    sitemap_enabled: bool
    robots_default: str
    robots_extra: str | None = None
    disallow_paths: list[str] = []


class SeoContentItem(BaseModel):
    entity_type: str
    entity_id: int
    title: str
    path: str
    status: str | None = None
    edit_href: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    meta_keywords: str | None = None
    canonical_url: str | None = None
    og_image: str | None = None
    robots: str | None = None
    schema_json: dict[str, Any] | None = None
    issues: list[str] = []
    score: int = 100


class SeoContentListResponse(BaseModel):
    items: list[SeoContentItem]


class SeoContentUpdate(BaseModel):
    meta_title: str | None = Field(default=None, max_length=255)
    meta_description: str | None = None
    meta_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=500)
    og_image: str | None = Field(default=None, max_length=500)
    robots: RobotsValue | None = None
    schema_json: dict[str, Any] | None = None
