from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import PlanPrice
from app.models.subscription import Subscription
from app.services.billing_summary_service import build_billing_summary
from app.services.subscription_service import get_active_subscription


def _subscription_payload(subscription: Subscription, plan_price: PlanPrice | None) -> dict:
    return {
        "id": subscription.id,
        "status": subscription.status,
        "billing_interval": subscription.billing_interval,
        "plan_name": subscription.plan.name if subscription.plan else "",
        "plan_slug": subscription.plan.slug if subscription.plan else "",
        "clinic_name": subscription.clinic_name,
        "current_period_start": subscription.current_period_start,
        "current_period_end": subscription.current_period_end,
        "amount": plan_price.amount if plan_price else Decimal("0"),
        "cancelled_at": subscription.cancelled_at,
        "cancel_at_period_end": subscription.status == "cancelled",
    }


def build_admin_customer_detail(db: Session, *, customer_id: int) -> dict:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError("Customer not found")

    subscriptions = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.plan_price))
        .filter(Subscription.customer_id == customer.id)
        .order_by(Subscription.created_at.desc())
        .all()
    )

    ord.= (
        db.query(Order)
        .filter(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer.id)
        .order_by(Payment.created_at.desc())
        .all()
    )

    credit_notes = (
        db.query(CreditNote)
        .filter(CreditNote.customer_id == customer.id)
        .order_by(CreditNote.created_at.desc())
        .all()
    )

    total_spent = (
        db.query(func.coalesce(func.sum(Payment.total), 0))
        .filter(Payment.customer_id == customer.id, Payment.status == "paid")
        .scalar()
    )

    active_subscription = get_active_subscription(db, customer.id)
    active_subscription_payload = None
    if active_subscription:
        plan_price = db.query(PlanPrice).filter(PlanPrice.id == active_subscription.plan_price_id).first()
        active_subscription_payload = _subscription_payload(active_subscription, plan_price)

    credit_note_items = []
    for note in credit_notes:
        payment = db.query(Payment).filter(Payment.id == note.payment_id).first()
        credit_note_items.append(
            {
                "id": note.id,
                "credit_note_number": note.credit_note_number,
                "invoice_number": payment.invoice_number if payment else "",
                "amount": note.amount,
                "reason": note.reason,
                "status": note.status,
                "pdf_path": note.pdf_path,
                "created_at": note.created_at,
            }
        )

    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "clinic_name": customer.clinic_name,
        "billing_address": customer.billing_address,
        "state": customer.state,
        "city": customer.city,
        "pincode": customer.pincode,
        "gstin": customer.gstin,
        "created_at": customer.created_at,
        "notify_email_billing": customer.notify_email_billing,
        "notify_email_marketing": customer.notify_email_marketing,
        "notify_sms_billing": customer.notify_sms_billing,
        "active_subscription": active_subscription_payload,
        "billing_summary": build_billing_summary(db, customer=customer),
        "subscriptions": [
            {
                "id": sub.id,
                "plan_name": sub.plan.name if sub.plan else "",
                "status": sub.status,
                "billing_interval": sub.billing_interval,
                "clinic_name": sub.clinic_name,
                "current_period_end": sub.current_period_end,
                "amount": sub.plan_price.amount if sub.plan_price else Decimal("0"),
            }
            for sub in subscriptions
        ],
        "recent_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_email": customer.email,
                "customer_name": customer.name,
                "order_type": order.order_type or "checkout",
                "status": order.status,
                "total": order.total,
                "coupon_code": order.coupon_code,
                "created_at": order.created_at,
            }
            for order in orders
        ],
        "recent_payments": [
            {
                "id": payment.id,
                "invoice_number": payment.invoice_number,
                "customer_email": customer.email,
                "total": payment.total,
                "status": payment.status,
                "payment_method": payment.payment_method,
                "paid_at": payment.paid_at,
            }
            for payment in payments
        ],
        "invoices": [
            {
                "id": payment.id,
                "invoice_number": payment.invoice_number,
                "subtotal": payment.subtotal,
                "cgst": payment.cgst,
                "sgst": payment.sgst,
                "igst": payment.igst,
                "gst_total": payment.gst_total,
                "total": payment.total,
                "status": payment.status,
                "payment_method": payment.payment_method,
                "pdf_path": payment.pdf_path,
                "paid_at": payment.paid_at,
                "created_at": payment.created_at,
            }
            for payment in payments
        ],
        "credit_notes": credit_note_items,
        "total_spent": Decimal(str(total_spent or 0)),
    }


def customer_has_purchase(db: Session, customer_id: int) -> bool:
    has_order = db.query(Order.id).filter(Order.customer_id == customer_id).first()
    if has_order:
        return True
    has_subscription = db.query(Subscription.id).filter(Subscription.customer_id == customer_id).first()
    if has_subscription:
        return True
    has_payment = (
        db.query(Payment.id)
        .filter(Payment.customer_id == customer_id, Payment.status == "paid")
        .first()
    )
    return bool(has_payment)
