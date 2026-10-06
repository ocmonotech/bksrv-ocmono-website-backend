import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.services.commerce_utils import generate_order_number, get_company_state
from app.services.coupon_service import CouponError, build_pricing, get_coupon
from app.services.payment_gateway import (
    create_gateway_order,
    get_payment_mode,
    get_razorpay_key_id,
    verify_razorpay_payment,
)


def _get_plan_price(db: Session, plan_slug: str, billing_interval: str) -> tuple[Plan, PlanPrice]:
    plan = db.query(Plan).filter(Plan.slug == plan_slug, Plan.is_active.is_(True)).first()
    if not plan:
        raise ValueError("Plan not found")

    plan_price = (
        db.query(PlanPrice)
        .filter(
            PlanPrice.plan_id == plan.id,
            PlanPrice.billing_interval == billing_interval,
            PlanPrice.is_active.is_(True),
        )
        .first()
    )
    if not plan_price:
        raise ValueError("Plan price not found")

    return plan, plan_price


def _resolve_pricing(db: Session, *, plan_price: PlanPrice, customer: Customer, billing_interval: str, coupon_code: str | None):
    coupon = get_coupon(db, coupon_code)
    try:
        return build_pricing(
            plan_amount=plan_price.amount,
            customer_state=customer.state,
            company_state=get_company_state(),
            coupon=coupon,
            billing_interval=billing_interval,
        )
    except CouponError as exc:
        raise ValueError(str(exc)) from exc


def preview_resubscribe(
    db: Session,
    *,
    customer: Customer,
    plan_slug: str,
    billing_interval: str,
    coupon_code: str | None = None,
) -> dict:
    plan, plan_price = _get_plan_price(db, plan_slug, billing_interval)
    pricing = _resolve_pricing(
        db,
        plan_price=plan_price,
        customer=customer,
        billing_interval=billing_interval,
        coupon_code=coupon_code,
    )
    return {
        "plan_slug": plan.slug,
        "plan_name": plan.name,
        "billing_interval": plan_price.billing_interval,
        **pricing,
    }


def initiate_resubscribe(
    db: Session,
    *,
    customer: Customer,
    plan_slug: str,
    billing_interval: str,
    coupon_code: str | None = None,
) -> dict:
    plan, plan_price = _get_plan_price(db, plan_slug, billing_interval)
    pricing = _resolve_pricing(
        db,
        plan_price=plan_price,
        customer=customer,
        billing_interval=billing_interval,
        coupon_code=coupon_code,
    )

    order_number = generate_order_number(db)
    gateway = create_gateway_order(
        order_number=order_number,
        total=pricing["total"],
        customer_email=customer.email,
        customer_phone=customer.phone or "",
    )

    order = Order(
        order_number=order_number,
        customer_id=customer.id,
        plan_price_id=plan_price.id,
        status="pending",
        subtotal=pricing["subtotal"],
        cgst=pricing["cgst"],
        sgst=pricing["sgst"],
        igst=pricing["igst"],
        gst_total=pricing["gst_total"],
        total=pricing["total"],
        coupon_code=pricing["coupon_code"],
        discount_amount=pricing["discount_amount"],
        trial_days=pricing["trial_days"],
        gateway_order_id=gateway["gateway_order_id"],
        order_type="resubscribe",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    if pricing["total"] <= 0:
        from app.services.order_fulfillment import fulfill_resubscribe_order

        result = fulfill_resubscribe_order(db, order=order)
        return {
            "applied_immediately": True,
            "message": "Subscription reactivated with your trial offer.",
            "subscription_id": result["subscription_id"],
            "current_period_end": result["current_period_end"],
            "total": order.total,
        }

    return {
        "applied_immediately": False,
        "order_id": order.id,
        "order_number": order.order_number,
        "total": order.total,
        "payment_mode": get_payment_mode(),
        "razorpay_key_id": gateway.get("razorpay_key_id") or get_razorpay_key_id(),
        "razorpay_order_id": gateway["gateway_order_id"],
        "amount_paise": gateway["amount_paise"],
        "message": "Complete payment to reactivate your subscription.",
    }


def confirm_resubscribe(
    db: Session,
    *,
    order: Order,
    customer: Customer,
    gateway_payment_id: str | None = None,
    razorpay_signature: str | None = None,
) -> dict:
    from app.services.order_fulfillment import fulfill_resubscribe_order

    if order.order_type != "resubscribe" or order.customer_id != customer.id:
        raise ValueError("Invalid resubscribe order")

    if order.status == "paid":
        return fulfill_resubscribe_order(db, order=order)

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
        payment_ref = gateway_payment_id or f"mock_resubscribe_{uuid.uuid4().hex[:12]}"

    return fulfill_resubscribe_order(db, order=order, gateway_payment_id=payment_ref)
