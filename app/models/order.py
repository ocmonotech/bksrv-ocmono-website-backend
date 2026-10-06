from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(30), nullable=False, unique=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_price_id = Column(Integer, ForeignKey("plan_prices.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending | paid | failed | cancelled
    subtotal = Column(Numeric(10, 2), nullable=False)
    cgst = Column(Numeric(10, 2), nullable=False, default=0)
    sgst = Column(Numeric(10, 2), nullable=False, default=0)
    igst = Column(Numeric(10, 2), nullable=False, default=0)
    gst_total = Column(Numeric(10, 2), nullable=False, default=0)
    total = Column(Numeric(10, 2), nullable=False)
    coupon_code = Column(String(30), nullable=True)
    discount_amount = Column(Numeric(10, 2), nullable=False, default=0)
    trial_days = Column(Integer, nullable=True)
    gateway_order_id = Column(String(100), nullable=True)
    order_type = Column(String(20), nullable=False, default="checkout")  # checkout | plan_change | resubscribe | renewal | retry_payment
    clinic_name = Column(String(180), nullable=True)
    addons_json = Column(String(2000), nullable=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    customer = relationship("Customer")
    plan_price = relationship("PlanPrice")
    payment = relationship("Payment", back_populates="order", uselist=False)
