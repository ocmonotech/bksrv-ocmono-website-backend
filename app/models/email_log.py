from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    template = Column(String(50), nullable=False, index=True)
    recipient = Column(String(150), nullable=False)
    subject = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="sent")  # sent | failed | mock
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
