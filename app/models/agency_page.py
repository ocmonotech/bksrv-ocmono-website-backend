from sqlalchemy import Column, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class AgencyPage(Base):
    __tablename__ = "agency_pages"

    id = Column(Integer, primary_key=True, index=True)
    page_type = Column(Enum("service", "project"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    excerpt = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    cover_image = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(Enum("draft", "published"), nullable=False, default="draft")
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(String(500), nullable=True)
    canonical_url = Column(String(500), nullable=True)
    og_image = Column(String(500), nullable=True)
    robots = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
