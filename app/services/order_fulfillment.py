import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.services.commerce_utils import generate_invoice_number
from app.services.coupon_service import get_coupon, increment_coupon_usage
from app.services.customer_auth import create_access_token
from app.services.email_service import send_commerce_admin_notification, send_payment_receipt_email, send_resubscribe_email, send_welcome_email
from app.services.invoice_pdf import generate_invoice_pdf
from app.services.payment_gateway import create_razorpay_subscription, get_payment_mode, get_razorpay_plan_id
from app.services.sms_service import send_sms


def _attach_gateway_subscription(db: Session, *, subscription: Subscription, customer: Customer, plan, plan_price: PlanPrice) -> None:
    razorpay_plan_id = get_razorpay_plan_id(plan.slug, plan_price.billing_interval)
    if get_payment_mode() != "razorpay" or not razorpay_plan_id:
        return

    try:
        gateway_sub = create_razorpay_subscription(
            razorpay_plan_id=razorpay_plan_id,
            customer_email=customer.email,
            customer_name=customer.name,
            customer_phone=customer.phone or "",
            total_count=120 if plan_price.billing_interval == "monthly" else 10,
        )
        subscription.gateway_subscription_id = gateway_sub["id"]
        db.commit()
    except Exception:
        pass


def fulfill_paid_order(
    db: Session,
    *,
    order: Order,
    gateway_payment_id: str | None = None,
) -> dict:
    if order.order_type == "resubscribe":
        return fulfill_resubscribe_order(db, order=order, gateway_payment_id=gateway_payment_id)
    if order.order_type == "retry_payment":
        from app.services.retry_payment_service import confirm_retry_payment

        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        result = confirm_retry_payment(
            db,
            order=order,
            customer=customer,
            gateway_payment_id=gateway_payment_id,
        )
        subscription = db.query(Subscription).filter(Subscription.id == result["subscription_id"]).first()
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "subscription_id": result["subscription_id"],
            "subscription_status": subscription.status if subscription else "",
        }
    if order.status == "paid":
        payment = db.query(Payment).filter(Payment.order_id == order.id).first()
        subscription = db.query(Subscription).filter(Subscription.order_id == order.id).first()
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "invoice_number": payment.invoice_number if payment else "",
            "subscription_id": subscription.id if subscription else 0,
            "subscription_status": subscription.status if subscription else "",
            "current_period_end": subscription.current_period_end if subscription else datetime.now(timezone.utc),
            "total": order.total,
            "access_token": create_access_token(customer.id, customer.email),
            "customer_email": customer.email,
        }

    if order.status != "pending":
        raise ValueError(f"Order cannot be paid (status: {order.status})")

    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    plan_price = db.query(PlanPrice).filter(PlanPrice.id == order.plan_price_id).first()
    plan = db.query(Plan).filter(Plan.id == plan_price.plan_id).first()

    now = datetime.now(timezone.utc)
    if order.trial_days:
        period_days = order.trial_days
    else:
        period_days = 365 if plan_price.billing_interval == "yearly" else 30

    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        plan_price_id=plan_price.id,
        order_id=order.id,
        clinic_name=order.clinic_name or customer.clinic_name,
        status="active",
        billing_interval=plan_price.billing_interval,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_days),
        gateway_subscription_id=gateway_payment_id or f"sub_{order.order_number}",
    )
    db.add(subscription)
    db.flush()
    _attach_gateway_subscription(db, subscription=subscription, customer=customer, plan=plan, plan_price=plan_price)

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
        gateway_payment_id=gateway_payment_id or f"pay_{order.order_number}",
        paid_at=now,
    )
    db.add(payment)
    db.flush()

    if order.total > 0:
        pdf_path = generate_invoice_pdf(
            payment=payment,
            customer=customer,
            plan=plan,
            billing_interval=plan_price.billing_interval,
        )
        payment.pdf_path = pdf_path

    order.status = "paid"
    coupon = get_coupon(db, order.coupon_code)
    increment_coupon_usage(db, coupon)
    db.commit()
    db.refresh(subscription)
    db.refresh(payment)

    uploads_root = Path(__file__).resolve().parents[2] / "uploads"
    send_welcome_email(db, customer, subscription, plan.name)
    if order.total > 0:
        send_payment_receipt_email(db, customer, payment, plan.name, uploads_root)
    if customer.phone:
        send_sms(
            db,
            phone=customer.phone,
            message=f"ClinicPro {plan.name} activated. Invoice {payment.invoice_number}. Total ₹ {order.total}.",
            template="payment_success",
            customer_id=customer.id,
            customer=customer,
            reference_type="payment",
            reference_id=payment.id,
        )
    send_commerce_admin_notification(
        db,
        order_number=order.order_number,
        order_type=order.order_type or "checkout",
        customer_name=customer.name,
        customer_email=customer.email,
        plan_name=plan.name,
        total=order.total,
        invoice_number=payment.invoice_number,
        order_id=order.id,
    )
    db.commit()

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "invoice_number": payment.invoice_number,
        "subscription_id": subscription.id,
        "subscription_status": subscription.status,
        "current_period_end": subscription.current_period_end,
        "total": order.total,
        "access_token": create_access_token(customer.id, customer.email),
        "customer_email": customer.email,
        "pdf_path": payment.pdf_path,
    }


def fulfill_resubscribe_order(
    db: Session,
    *,
    order: Order,
    gateway_payment_id: str | None = None,
) -> dict:
    if order.status == "paid":
        payment = db.query(Payment).filter(Payment.order_id == order.id).first()
        subscription = db.query(Subscription).filter(Subscription.id == payment.subscription_id).first() if payment else None
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "invoice_number": payment.invoice_number if payment else "",
            "subscription_id": subscription.id if subscription else 0,
            "subscription_status": subscription.status if subscription else "",
            "current_period_end": subscription.current_period_end if subscription else datetime.now(timezone.utc),
            "total": order.total,
            "access_token": create_access_token(customer.id, customer.email),
            "customer_email": customer.email,
        }

    if order.status != "pending":
        raise ValueError(f"Order cannot be paid (status: {order.status})")

    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    plan_price = db.query(PlanPrice).filter(PlanPrice.id == order.plan_price_id).first()
    plan = db.query(Plan).filter(Plan.id == plan_price.plan_id).first()

    now = datetime.now(timezone.utc)
    period_days = order.trial_days or (365 if plan_price.billing_interval == "yearly" else 30)

    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        plan_price_id=plan_price.id,
        order_id=order.id,
        clinic_name=order.clinic_name or customer.clinic_name,
        status="active",
        billing_interval=plan_price.billing_interval,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_days),
        gateway_subscription_id=gateway_payment_id or f"sub_{order.order_number}",
    )
    db.add(subscription)
    db.flush()
    _attach_gateway_subscription(db, subscription=subscription, customer=customer, plan=plan, plan_price=plan_price)

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
        gateway_payment_id=gateway_payment_id or f"pay_{order.order_number}",
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
    coupon = get_coupon(db, order.coupon_code)
    increment_coupon_usage(db, coupon)
    db.commit()
    db.refresh(subscription)
    db.refresh(payment)

    uploads_root = Path(__file__).resolve().parents[2] / "uploads"
    send_resubscribe_email(db, customer, subscription, plan.name)
    if order.total > 0:
        send_payment_receipt_email(db, customer, payment, plan.name, uploads_root)
    if customer.phone:
        send_sms(
            db,
            phone=customer.phone,
            message=f"ClinicPro {plan.name} is active again. Invoice {payment.invoice_number}.",
            template="resubscribe_success",
            customer_id=customer.id,
            customer=customer,
            reference_type="payment",
            reference_id=payment.id,
        )
    send_commerce_admin_notification(
        db,
        order_number=order.order_number,
        order_type=order.order_type or "resubscribe",
        customer_name=customer.name,
        customer_email=customer.email,
        plan_name=plan.name,
        total=order.total,
        invoice_number=payment.invoice_number,
        order_id=order.id,
    )
    db.commit()

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "invoice_number": payment.invoice_number,
        "subscription_id": subscription.id,
        "subscription_status": subscription.status,
        "current_period_end": subscription.current_period_end,
        "total": order.total,
        "access_token": create_access_token(customer.id, customer.email),
        "customer_email": customer.email,
        "pdf_path": payment.pdf_path,
    }
