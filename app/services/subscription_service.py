from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.services.commerce_utils import as_utc
from app.services.email_service import send_cancellation_email, send_plan_change_email, send_reactivation_email


def get_active_subscription(db: Session, customer_id: int) -> Subscription | None:
    now = datetime.now(timezone.utc)
    subscriptions = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(
            Subscription.customer_id == customer_id,
            Subscription.status.in_(["active", "cancelled", "past_due"]),
        )
        .order_by(Subscription.created_at.desc())
        .all()
    )
    for subscription in subscriptions:
        if as_utc(subscription.current_period_end) >= now:
            return subscription
    return None


def list_customer_subscriptions(db: Session, customer_id: int) -> list[Subscription]:
    return (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.plan_price))
        .filter(Subscription.customer_id == customer_id)
        .order_by(Subscription.created_at.desc())
        .all()
    )


def get_customer_subscription(
    db: Session,
    customer_id: int,
    subscription_id: int | None = None,
) -> Subscription | None:
    if subscription_id is None:
        return get_active_subscription(db, customer_id)

    subscription = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(Subscription.id == subscription_id, Subscription.customer_id == customer_id)
        .first()
    )
    if not subscription:
        return None

    now = datetime.now(timezone.utc)
    if subscription.status in {"active", "cancelled", "past_due"} and as_utc(subscription.current_period_end) >= now:
        return subscription
    if subscription.status == "past_due":
        return subscription
    return subscription


def cancel_subscription(db: Session, subscription: Subscription, customer: Customer) -> Subscription:
    if subscription.status not in {"active", "past_due"}:
        raise ValueError("Only active subscriptions can be cancelled")

    now = datetime.now(timezone.utc)
    subscription.status = "cancelled"
    subscription.cancelled_at = now
    db.commit()
    db.refresh(subscription)

    send_cancellation_email(db, customer, subscription, subscription.plan.name)
    db.commit()
    return subscription


def get_cancelled_subscription(db: Session, customer_id: int) -> Subscription | None:
    now = datetime.now(timezone.utc)
    subscriptions = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(
            Subscription.customer_id == customer_id,
            Subscription.status == "cancelled",
        )
        .order_by(Subscription.created_at.desc())
        .all()
    )
    for subscription in subscriptions:
        if as_utc(subscription.current_period_end) >= now:
            return subscription
    return None


def reactivate_subscription(db: Session, subscription: Subscription, customer: Customer) -> Subscription:
    if subscription.status != "cancelled":
        raise ValueError("Only cancelled subscriptions can be reactivated")

    now = datetime.now(timezone.utc)
    if as_utc(subscription.current_period_end) < now:
        raise ValueError("Subscription period has expired. Please resubscribe instead.")

    subscription.status = "active"
    subscription.cancelled_at = None
    db.commit()
    db.refresh(subscription)

    send_reactivation_email(db, customer, subscription, subscription.plan.name if subscription.plan else "ClinicPro")
    db.commit()
    return subscription


def change_subscription_plan(
    db: Session,
    subscription: Subscription,
    customer: Customer,
    *,
    plan_slug: str,
    billing_interval: str,
) -> Subscription:
    if subscription.status not in {"active", "cancelled", "past_due"}:
        raise ValueError("Subscription cannot be changed")

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

    old_plan_name = subscription.plan.name if subscription.plan else "Previous plan"
    subscription.plan_id = plan.id
    subscription.plan_price_id = plan_price.id
    subscription.billing_interval = billing_interval
    subscription.status = "active"
    subscription.cancelled_at = None
    subscription.plan = plan
    db.commit()
    db.refresh(subscription)

    send_plan_change_email(db, customer, subscription, old_plan_name, plan.name)
    db.commit()
    return subscription
