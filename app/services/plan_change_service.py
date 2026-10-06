import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.services.commerce_utils import generate_invoice_number, generate_order_number, get_company_state
from app.services.email_service import send_payment_receipt_email, send_plan_change_email
from app.services.invoice_pdf import generate_invoice_pdf
from app.services.payment_gateway import (
    create_gateway_order,
    get_payment_mode,
    get_razorpay_key_id,
    verify_razorpay_payment,
)
from app.services.proration_service import calculate_plan_change_proration
from app.services.sms_service import send_sms


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


def preview_plan_change(
    db: Session,
    *,
    subscription: Subscription,
    customer: Customer,
    plan_slug: str,
    billing_interval: str,
) -> dict:
    plan, new_plan_price = _get_plan_price(db, plan_slug, billing_interval)
    old_plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
    if not old_plan_price:
        raise ValueError("Current plan price not found")

    proration = calculate_plan_change_proration(
        subscription=subscription,
        old_plan_price=old_plan_price,
        new_plan_price=new_plan_price,
        customer_state=customer.state,
        company_state=get_company_state(),
    )

    return {
        "current_plan_name": subscription.plan.name if subscription.plan else "",
        "current_plan_slug": subscription.plan.slug if subscription.plan else "",
        "current_billing_interval": subscription.billing_interval,
        "new_plan_name": plan.name,
        "new_plan_slug": plan.slug,
        "new_billing_interval": billing_interval,
        **proration,
    }


def apply_plan_change_immediately(
    db: Session,
    *,
    subscription: Subscription,
    customer: Customer,
    plan: Plan,
    plan_price: PlanPrice,
    reset_period: bool,
) -> Subscription:
    old_plan_name = subscription.plan.name if subscription.plan else "Previous plan"
    now = datetime.now(timezone.utc)

    subscription.plan_id = plan.id
    subscription.plan_price_id = plan_price.id
    subscription.billing_interval = plan_price.billing_interval
    subscription.status = "active"
    subscription.cancelled_at = None

    if reset_period:
        period_days = 365 if plan_price.billing_interval == "yearly" else 30
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=period_days)

    db.commit()
    db.refresh(subscription)

    send_plan_change_email(db, customer, subscription, old_plan_name, plan.name)
    db.commit()
    return subscription


def initiate_plan_change(
    db: Session,
    *,
    subscription: Subscription,
    customer: Customer,
    plan_slug: str,
    billing_interval: str,
) -> dict:
    preview = preview_plan_change(
        db,
        subscription=subscription,
        customer=customer,
        plan_slug=plan_slug,
        billing_interval=billing_interval,
    )

    if preview["same_selection"]:
        raise ValueError("You are already on this plan and billing interval")

    plan, plan_price = _get_plan_price(db, plan_slug, billing_interval)

    if not preview["requires_payment"]:
        updated = apply_plan_change_immediately(
            db,
            subscription=subscription,
            customer=customer,
            plan=plan,
            plan_price=plan_price,
            reset_period=preview["reset_period"],
        )
        message = "Plan updated immediately."
        if preview["is_downgrade"]:
            message = "Plan downgraded. The change applies immediately with no additional charge."
        return {
            "applied_immediately": True,
            "subscription": updated,
            "message": message,
        }

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
        plan_price_id=plan_price.id,
        status="pending",
        subtotal=preview["subtotal"],
        cgst=preview["cgst"],
        sgst=preview["sgst"],
        igst=preview["igst"],
        gst_total=preview["gst_total"],
        total=preview["total"],
        gateway_order_id=gateway["gateway_order_id"],
        order_type="plan_change",
        subscription_id=subscription.id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "applied_immediately": False,
        "order_id": order.id,
        "order_number": order.order_number,
        "total": order.total,
        "payment_mode": get_payment_mode(),
        "razorpay_key_id": gateway.get("razorpay_key_id") or get_razorpay_key_id(),
        "razorpay_order_id": gateway["gateway_order_id"],
        "amount_paise": gateway["amount_paise"],
        "message": "Complete payment to confirm your plan change.",
    }


def confirm_plan_change(
    db: Session,
    *,
    order: Order,
    customer: Customer,
    gateway_payment_id: str | None = None,
    razorpay_signature: str | None = None,
) -> Subscription:
    if order.order_type != "plan_change" or not order.subscription_id:
        raise ValueError("Invalid plan change order")

    if order.status == "paid":
        subscription = (
            db.query(Subscription)
            .options(joinedload(Subscription.plan))
            .filter(Subscription.id == order.subscription_id)
            .first()
        )
        return subscription

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
        payment_ref = gateway_payment_id or f"mock_plan_change_{uuid.uuid4().hex[:12]}"

    subscription = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(Subscription.id == order.subscription_id, Subscription.customer_id == customer.id)
        .first()
    )
    if not subscription:
        raise ValueError("Subscription not found")

    plan_price = db.query(PlanPrice).filter(PlanPrice.id == order.plan_price_id).first()
    plan = db.query(Plan).filter(Plan.id == plan_price.plan_id).first()
    old_plan_name = subscription.plan.name if subscription.plan else "Previous plan"
    interval_changed = subscription.billing_interval != plan_price.billing_interval
    now = datetime.now(timezone.utc)

    subscription.plan_id = plan.id
    subscription.plan_price_id = plan_price.id
    subscription.billing_interval = plan_price.billing_interval
    subscription.status = "active"
    subscription.cancelled_at = None

    if interval_changed:
        period_days = 365 if plan_price.billing_interval == "yearly" else 30
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=period_days)

    payment = Payment(
        invoice_number=generate_invoice_number(db),
        order_id=order.id,
        customer_id=customer.id,
        subscription_id=subscription.id,
        subtotal=order.subtotal,
        cgst=order.cgst,
        sgst=order.sgst,
        igst=order.igst,
        gst_total=order.gst_total,
        total=order.total,
        status="paid",
        payment_method=get_payment_mode(),
        gateway_payment_id=payment_ref,
        paid_at=now,
    )
    db.add(payment)
    db.flush()

    if order.total > 0:
        payment.pdf_path = generate_invoice_pdf(
            payment=payment,
            customer=customer,
            plan=plan,
            billing_interval=plan_price.billing_interval,
        )

    order.status = "paid"
    db.commit()
    db.refresh(subscription)
    db.refresh(payment)

    uploads_root = Path(__file__).resolve().parents[2] / "uploads"
    send_plan_change_email(db, customer, subscription, old_plan_name, plan.name)
    if order.total > 0:
        send_payment_receipt_email(db, customer, payment, plan.name, uploads_root)
    if customer.phone:
        send_sms(
            db,
            phone=customer.phone,
            message=f"ClinicPro plan updated to {plan.name}. Prorated charge ₹ {order.total}.",
            template="plan_change",
            customer_id=customer.id,
            customer=customer,
            reference_type="subscription",
            reference_id=subscription.id,
        )
    db.commit()
    return subscription
