from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class ContactSubmission(Base):
    __tablename__ = "contact_submissions"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(150), nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    clinic_name = Column(String(180), nullable=False)
    inquiry_type = Column(String(80), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="new")  # new | read | responded
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
