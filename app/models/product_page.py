from sqlalchemy import Column, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class ProductPage(Base):
    __tablename__ = "product_pages"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(
        Enum(
            "apps-tools",
            "practice-types",
            "multi-clinic",
            "portfolio-applications",
            "portfolio-websites",
            "saas-product",
        ),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    image = Column(String(500), nullable=True)
    link = Column(String(500), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(Enum("draft", "published"), nullable=False, default="draft")
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(String(500), nullable=True)
    canonical_url = Column(String(500), nullable=True)
    og_image = Column(String(500), nullable=True)
    robots = Column(String(50), nullable=True)
    schema_json = Column(JSON, nullable=True)
    capabilities_json = Column(JSON, nullable=True)
    # Drupal-like field bundle for SaaS content type (pricing, CTAs, industry, etc.)
    saas_meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
