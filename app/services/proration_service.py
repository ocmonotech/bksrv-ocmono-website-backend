from datetime import datetime, timezone
from decimal import Decimal

from app.models.plan import PlanPrice
from app.models.subscription import Subscription
from app.services.gst import GstBreakdown, calculate_gst


def _period_days(billing_interval: str) -> int:
    return 365 if billing_interval == "yearly" else 30


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def calculate_plan_change_proration(
    *,
    subscription: Subscription,
    old_plan_price: PlanPrice,
    new_plan_price: PlanPrice,
    customer_state: str,
    company_state: str,
) -> dict:
    now = datetime.now(timezone.utc)
    period_start = _as_utc(subscription.current_period_start)
    period_end = _as_utc(subscription.current_period_end)

    total_days = max(1, (period_end - period_start).days)
    days_remaining = max(0, (period_end - now).days)
    if days_remaining == 0 and now < period_end:
        days_remaining = 1

    old_amount = Decimal(str(old_plan_price.amount))
    new_amount = Decimal(str(new_plan_price.amount))

    old_daily = old_amount / Decimal(total_days)
    new_daily = new_amount / Decimal(_period_days(new_plan_price.billing_interval))

    credit_amount = (old_daily * Decimal(days_remaining)).quantize(Decimal("0.01"))
    charge_amount = (new_daily * Decimal(days_remaining)).quantize(Decimal("0.01"))
    net_subtotal = max(Decimal("0.00"), (charge_amount - credit_amount).quantize(Decimal("0.01")))

    gst: GstBreakdown = calculate_gst(net_subtotal, customer_state, company_state)
    interval_changed = subscription.billing_interval != new_plan_price.billing_interval
    same_selection = (
        subscription.plan_id == new_plan_price.plan_id
        and subscription.billing_interval == new_plan_price.billing_interval
    )

    return {
        "days_remaining": days_remaining,
        "credit_amount": credit_amount,
        "charge_amount": charge_amount,
        "subtotal": gst["subtotal"],
        "cgst": gst["cgst"],
        "sgst": gst["sgst"],
        "igst": gst["igst"],
        "gst_total": gst["gst_total"],
        "total": gst["total"],
        "is_intra_state": gst["is_intra_state"],
        "requires_payment": net_subtotal > 0 and not same_selection,
        "is_downgrade": charge_amount < credit_amount and not same_selection,
        "interval_changed": interval_changed,
        "reset_period": interval_changed,
        "same_selection": same_selection,
    }
