from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.subscription import Subscription
from app.services.commerce_utils import as_utc
from app.services.renewal_service import renew_subscription
from app.services.subscription_service import cancel_subscription, reactivate_subscription


def _load_subscription(db: Session, subscription_id: int) -> Subscription:
    subscription = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.customer))
        .filter(Subscription.id == subscription_id)
        .first()
    )
    if not subscription:
        raise ValueError("Subscription not found")
    return subscription


def extend_subscription(db: Session, *, subscription_id: int, days: int) -> Subscription:
    if days < 1 or days > 365:
        raise ValueError("Extension must be between 1 and 365 days")

    subscription = _load_subscription(db, subscription_id)
    now = datetime.now(timezone.utc)
    period_end = as_utc(subscription.current_period_end)

    if period_end < now:
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=days)
    else:
        subscription.current_period_end = period_end + timedelta(days=days)

    subscription.status = "active"
    subscription.cancelled_at = None
    db.commit()
    db.refresh(subscription)
    return subscription


def admin_cancel_subscription(db: Session, *, subscription_id: int) -> Subscription:
    subscription = _load_subscription(db, subscription_id)
    if subscription.status in {"expired", "cancelled"}:
        return subscription

    if not subscription.customer:
        raise ValueError("Customer not found for subscription")

    return cancel_subscription(db, subscription, subscription.customer)


def admin_reactivate_subscription(db: Session, *, subscription_id: int) -> Subscription:
    subscription = _load_subscription(db, subscription_id)
    if subscription.status == "active":
        return subscription

    if not subscription.customer:
        raise ValueError("Customer not found for subscription")

    now = datetime.now(timezone.utc)
    if as_utc(subscription.current_period_end) < now:
        raise ValueError("Subscription period has expired. Extend the period or trigger a renewal first.")

    if subscription.status != "cancelled":
        subscription.status = "active"
        subscription.cancelled_at = None
        db.commit()
        db.refresh(subscription)
        return subscription

    return reactivate_subscription(db, subscription, subscription.customer)


def admin_renew_subscription(db: Session, *, subscription_id: int) -> dict:
    subscription = _load_subscription(db, subscription_id)
    if subscription.status == "expired" or as_utc(subscription.current_period_end) < datetime.now(timezone.utc):
        subscription.status = "active"

    payment = renew_subscription(db, subscription=subscription)
    db.refresh(subscription)
    return {
        "subscription_id": subscription.id,
        "subscription_status": subscription.status,
        "current_period_end": subscription.current_period_end,
        "payment_id": payment.id,
        "invoice_number": payment.invoice_number,
        "total": payment.total,
    }
