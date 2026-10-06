from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.payment import Payment
from app.models.plan import PlanPrice
from app.models.subscription import Subscription
from app.services.payment_gateway import get_payment_mode
from app.services.subscription_service import get_active_subscription


def build_billing_summary(db: Session, *, customer: Customer) -> dict:
    subscription = get_active_subscription(db, customer.id)
    last_payment = (
        db.query(Payment)
        .filter(Payment.customer_id == customer.id, Payment.status == "paid")
        .order_by(Payment.paid_at.desc())
        .first()
    )
    total_spent = (
        db.query(func.coalesce(func.sum(Payment.total), 0))
        .filter(Payment.customer_id == customer.id, Payment.status == "paid")
        .scalar()
    )

    payment_mode = get_payment_mode()
    payment_labels = {
        "mock": "Demo / mock payment",
        "razorpay": "Razorpay (card, UPI, netbanking)",
    }

    next_renewal_amount = None
    plan_name = None
    billing_interval = None
    subscription_status = None

    if subscription:
        plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
        if plan_price:
            next_renewal_amount = plan_price.amount
        plan_name = subscription.plan.name if subscription.plan else None
        billing_interval = subscription.billing_interval
        subscription_status = subscription.status

    return {
        "payment_method": payment_mode,
        "payment_method_label": payment_labels.get(payment_mode, payment_mode.title()),
        "has_active_subscription": subscription is not None and subscription.status == "active",
        "subscription_status": subscription_status,
        "plan_name": plan_name,
        "billing_interval": billing_interval,
        "next_renewal_date": subscription.current_period_end if subscription else None,
        "next_renewal_amount": next_renewal_amount,
        "last_invoice_number": last_payment.invoice_number if last_payment else None,
        "last_payment_date": last_payment.paid_at if last_payment else None,
        "last_payment_amount": last_payment.total if last_payment else None,
        "total_spent": total_spent or 0,
        "invoice_count": db.query(Payment).filter(Payment.customer_id == customer.id, Payment.status == "paid").count(),
    }
