from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    logo = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True, default="General")
    external_url = Column(String(500), nullable=True)
    card_color = Column(Integer, nullable=False, default=1)
    sort_order = Column(Integer, nullable=False, default=0)
    show_in_carousel = Column(Boolean, nullable=False, default=False)
    status = Column(Enum("draft", "published"), nullable=False, default="draft")
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_keywords = Column(String(500), nullable=True)
    canonical_url = Column(String(500), nullable=True)
    og_image = Column(String(500), nullable=True)
    robots = Column(String(50), nullable=True)
    schema_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
