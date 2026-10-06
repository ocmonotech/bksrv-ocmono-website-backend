from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Profession(Base):
    __tablename__ = "professions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    image = Column(String(500), nullable=True)
    mega_menu_column = Column(Integer, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    show_on_homepage = Column(Boolean, nullable=False, default=False)
    animation_delay = Column(String(10), nullable=True)
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
