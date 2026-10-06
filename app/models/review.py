from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(Enum("testimonial", "google"), nullable=False, default="testimonial")
    google_review_id = Column(String(255), nullable=True, unique=True, index=True)
    author_name = Column(String(120), nullable=False)
    author_role = Column(String(120), nullable=True)
    clinic_name = Column(String(180), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    rating = Column(Integer, nullable=False, default=5)
    review_text = Column(Text, nullable=False)
    review_url = Column(String(500), nullable=True)
    consent_given = Column(Boolean, nullable=False, default=False)
    status = Column(Enum("pending", "approved", "rejected"), nullable=False, default="pending")
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
