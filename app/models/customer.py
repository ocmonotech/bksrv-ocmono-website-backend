from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=True)
    clinic_name = Column(String(180), nullable=True)
    gstin = Column(String(15), nullable=True)
    billing_address = Column(String(500), nullable=True)
    state = Column(String(100), nullable=False, default="Maharashtra")
    city = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    notify_email_billing = Column(Boolean, nullable=False, default=True)
    notify_email_marketing = Column(Boolean, nullable=False, default=False)
    notify_sms_billing = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
