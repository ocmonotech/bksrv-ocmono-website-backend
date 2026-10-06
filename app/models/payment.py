from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(30), nullable=False, unique=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    subtotal = Column(Numeric(10, 2), nullable=False)
    cgst = Column(Numeric(10, 2), nullable=False, default=0)
    sgst = Column(Numeric(10, 2), nullable=False, default=0)
    igst = Column(Numeric(10, 2), nullable=False, default=0)
    gst_total = Column(Numeric(10, 2), nullable=False, default=0)
    total = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="paid")  # paid | failed | refunded
    payment_method = Column(String(50), nullable=False, default="mock")
    gateway_payment_id = Column(String(100), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="payment")
    customer = relationship("Customer")
    subscription = relationship("Subscription")
