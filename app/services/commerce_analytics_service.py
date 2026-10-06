from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.order import Order
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.services.commerce_utils import as_utc


def _monthly_amount(amount: Decimal, billing_interval: str) -> Decimal:
    if billing_interval == "yearly":
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    return Decimal(str(amount)).quantize(Decimal("0.01"))


def build_commerce_analytics(db: Session, *, months: int = 6) -> dict:
    now = datetime.now(timezone.utc)
    month_starts: list[datetime] = []
    for offset in range(months - 1, -1, -1):
        year = now.year
        month = now.month - offset
        while month <= 0:
            month += 12
            year -= 1
        month_starts.append(datetime(year, month, 1, tzinfo=timezone.utc))

    payments = db.query(Payment).filter(Payment.status == "paid", Payment.paid_at.isnot(None)).all()

    revenue_by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for payment in payments:
        paid_at = as_utc(payment.paid_at)
        revenue_by_month[paid_at.strftime("%Y-%m")] += Decimal(str(payment.total))

    revenue_series = [
        {
            "month": start.strftime("%b %Y"),
            "month_key": start.strftime("%Y-%m"),
            "revenue": revenue_by_month.get(start.strftime("%Y-%m"), Decimal("0")),
        }
        for start in month_starts
    ]

    subs = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.plan_price))
        .all()
    )
    status_counts = Counter(sub.status for sub in subs)
    plan_counts = Counter(sub.plan.name for sub in subs if sub.plan)

    active_subs = [sub for sub in subs if sub.status == "active" and sub.plan_price]
    mrr = sum(_monthly_amount(sub.plan_price.amount, sub.billing_interval) for sub in active_subs)

    window_start = now - timedelta(days=30)
    churned = 0
    for sub in subs:
        if sub.status not in {"cancelled", "expired"}:
            continue
        churn_at = sub.cancelled_at or sub.current_period_end
        if as_utc(churn_at) >= window_start:
            churned += 1

    eligible = len(subs) or 1
    churn_rate = Decimal(str(round(churned / eligible * 100, 1)))

    current_month_key = now.strftime("%Y-%m")
    revenue_this_month = revenue_by_month.get(current_month_key, Decimal("0"))
    arpu = (mrr / len(active_subs)).quantize(Decimal("0.01")) if active_subs else Decimal("0")

    order_breakdown = (
        db.query(Order.order_type, func.count(Order.id))
        .filter(Order.status == "paid")
        .group_by(Order.order_type)
        .all()
    )

    return {
        "revenue_series": revenue_series,
        "revenue_this_month": revenue_this_month,
        "mrr": mrr,
        "arpu": arpu,
        "churn_rate_30d": churn_rate,
        "subscription_status": dict(status_counts),
        "plan_distribution": dict(plan_counts),
        "order_type_breakdown": {row[0] or "checkout": row[1] for row in order_breakdown},
        "total_paid_invoices": db.query(Payment).filter(Payment.status == "paid").count(),
        "refunded_invoices": db.query(Payment).filter(Payment.status == "refunded").count(),
    }
