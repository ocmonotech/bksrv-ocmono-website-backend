from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class SeoSiteSettings(Base):
    __tablename__ = "seo_site_settings"

    id = Column(Integer, primary_key=True, index=True)
    site_name = Column(String(255), nullable=False, default="OCMONO")
    title_suffix = Column(String(255), nullable=True, default="OCMONO")
    default_meta_description = Column(Text, nullable=True)
    default_og_image = Column(String(500), nullable=True)
    twitter_handle = Column(String(100), nullable=True)
    robots_default = Column(String(50), nullable=False, default="index,follow")
    google_site_verification = Column(String(255), nullable=True)
    bing_site_verification = Column(String(255), nullable=True)
    organization_schema = Column(JSON, nullable=True)
    sitemap_enabled = Column(Boolean, nullable=False, default=True)
    robots_extra = Column(Text, nullable=True)
    gtm_enabled = Column(Boolean, nullable=False, default=False)
    gtm_container_id = Column(String(50), nullable=True)
    ga4_enabled = Column(Boolean, nullable=False, default=False)
    ga4_measurement_id = Column(String(50), nullable=True)
    meta_pixel_enabled = Column(Boolean, nullable=False, default=False)
    meta_pixel_id = Column(String(50), nullable=True)
    linkedin_enabled = Column(Boolean, nullable=False, default=False)
    linkedin_partner_id = Column(String(50), nullable=True)
    clarity_enabled = Column(Boolean, nullable=False, default=False)
    clarity_project_id = Column(String(50), nullable=True)
    custom_head_scripts = Column(Text, nullable=True)
    custom_body_scripts = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SeoPage(Base):
    """SEO overrides for static / CMS routes (home, about, pricing, etc.)."""

    __tablename__ = "seo_pages"
    __table_args__ = (UniqueConstraint("path", name="uq_seo_pages_path"),)

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(500), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(String(500), nullable=True)
    canonical_url = Column(String(500), nullable=True)
    og_image = Column(String(500), nullable=True)
    robots = Column(String(50), nullable=True)
    schema_json = Column(JSON, nullable=True)
    sitemap_include = Column(Boolean, nullable=False, default=True)
    sitemap_priority = Column(String(10), nullable=True, default="0.7")
    sitemap_changefreq = Column(String(20), nullable=True, default="weekly")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class SeoRedirect(Base):
    __tablename__ = "seo_redirects"
    __table_args__ = (UniqueConstraint("from_path", name="uq_seo_redirects_from_path"),)

    id = Column(Integer, primary_key=True, index=True)
    from_path = Column(String(500), nullable=False, index=True)
    to_path = Column(String(1000), nullable=False)
    status_code = Column(Integer, nullable=False, default=301)
    is_active = Column(Boolean, nullable=False, default=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
