import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.order import Order
from app.models.subscription import Subscription
from app.services.commerce_utils import generate_order_number, get_company_state
from app.services.coupon_service import build_pricing
from app.services.payment_gateway import (
    create_gateway_order,
    get_payment_mode,
    get_razorpay_key_id,
    verify_razorpay_payment,
)
from app.services.renewal_service import renew_subscription


def get_retryable_subscription(db: Session, customer_id: int) -> Subscription | None:
    return (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.plan_price))
        .filter(
            Subscription.customer_id == customer_id,
            Subscription.status == "past_due",
        )
        .order_by(Subscription.created_at.desc())
        .first()
    )


def preview_retry_payment(db: Session, *, customer: Customer, subscription: Subscription) -> dict:
    if not subscription.plan_price:
        raise ValueError("Subscription plan price not found")

    pricing = build_pricing(
        plan_amount=subscription.plan_price.amount,
        customer_state=customer.state,
        company_state=get_company_state(),
        coupon=None,
        billing_interval=subscription.billing_interval,
    )
    return {
        "plan_slug": subscription.plan.slug,
        "plan_name": subscription.plan.name,
        "billing_interval": subscription.billing_interval,
        **pricing,
    }


def initiate_retry_payment(db: Session, *, customer: Customer, subscription: Subscription) -> dict:
    preview = preview_retry_payment(db, customer=customer, subscription=subscription)
    order_number = generate_order_number(db)
    gateway = create_gateway_order(
        order_number=order_number,
        total=preview["total"],
        customer_email=customer.email,
        customer_phone=customer.phone or "",
    )

    order = Order(
        order_number=order_number,
        customer_id=customer.id,
        plan_price_id=subscription.plan_price_id,
        status="pending",
        subtotal=preview["subtotal"],
        cgst=preview["cgst"],
        sgst=preview["sgst"],
        igst=preview["igst"],
        gst_total=preview["gst_total"],
        total=preview["total"],
        discount_amount=0,
        gateway_order_id=gateway["gateway_order_id"],
        order_type="retry_payment",
        subscription_id=subscription.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "total": order.total,
        "payment_mode": get_payment_mode(),
        "razorpay_key_id": gateway.get("razorpay_key_id") or get_razorpay_key_id(),
        "razorpay_order_id": gateway["gateway_order_id"],
        "amount_paise": gateway["amount_paise"],
        "message": "Complete payment to restore your subscription.",
    }


def confirm_retry_payment(
    db: Session,
    *,
    order: Order,
    customer: Customer,
    gateway_payment_id: str | None = None,
    razorpay_signature: str | None = None,
) -> dict:
    if order.order_type != "retry_payment" or order.customer_id != customer.id:
        raise ValueError("Invalid retry payment order")

    if order.status == "paid":
        subscription = db.query(Subscription).filter(Subscription.id == order.subscription_id).first()
        if subscription:
            return {"subscription_id": subscription.id, "status": subscription.status}
        return {"subscription_id": 0, "status": "unknown"}

    if order.status != "pending":
        raise ValueError(f"Order cannot be paid (status: {order.status})")

    if order.total > 0 and get_payment_mode() == "razorpay":
        if not gateway_payment_id or not razorpay_signature:
            raise ValueError("Razorpay payment details are required")
        if not verify_razorpay_payment(
            gateway_order_id=order.gateway_order_id,
            gateway_payment_id=gateway_payment_id,
            signature=razorpay_signature,
        ):
            raise ValueError("Payment verification failed")
        payment_ref = gateway_payment_id
    else:
        payment_ref = gateway_payment_id or f"mock_retry_{uuid.uuid4().hex[:12]}"

    subscription = db.query(Subscription).filter(Subscription.id == order.subscription_id).first()
    if not subscription:
        raise ValueError("Subscription not found")

    order.status = "paid"
    db.commit()

    renew_subscription(db, subscription=subscription, gateway_payment_id=payment_ref, order=order)
    db.refresh(subscription)
    return {"subscription_id": subscription.id, "status": subscription.status}
