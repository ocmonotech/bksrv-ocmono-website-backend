from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.coupon import Coupon
from app.services.gst import calculate_gst


class CouponError(Exception):
    pass


def get_coupon(db: Session, code: str | None) -> Coupon | None:
    if not code or not code.strip():
        return None
    return db.query(Coupon).filter(Coupon.code == code.strip().upper(), Coupon.is_active.is_(True)).first()


def validate_coupon(
    coupon: Coupon,
    *,
    billing_interval: str,
) -> None:
    now = datetime.now(timezone.utc)
    if coupon.valid_until:
        valid_until = coupon.valid_until
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        if valid_until < now:
            raise CouponError("This coupon has expired")
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise CouponError("This coupon has reached its usage limit")
    if coupon.billing_interval and coupon.billing_interval != billing_interval:
        raise CouponError(f"This coupon is valid for {coupon.billing_interval} billing only")


def apply_coupon_to_subtotal(
    subtotal: Decimal | float,
    coupon: Coupon | None,
) -> tuple[Decimal, Decimal, int | None]:
    amount = Decimal(str(subtotal)).quantize(Decimal("0.01"))
    if not coupon:
        return amount, Decimal("0.00"), None

    if coupon.discount_type == "percent":
        discount = (amount * (Decimal(str(coupon.discount_value)) / Decimal("100"))).quantize(Decimal("0.01"))
    else:
        discount = Decimal(str(coupon.discount_value)).quantize(Decimal("0.01"))

    discount = min(discount, amount)
    discounted = (amount - discount).quantize(Decimal("0.01"))
    return discounted, discount, coupon.trial_days


def build_pricing(
    *,
    plan_amount: Decimal | float,
    customer_state: str,
    company_state: str,
    coupon: Coupon | None = None,
    billing_interval: str,
) -> dict:
    if coupon:
        validate_coupon(coupon, billing_interval=billing_interval)

    discounted_subtotal, discount_amount, trial_days = apply_coupon_to_subtotal(plan_amount, coupon)
    gst = calculate_gst(discounted_subtotal, customer_state, company_state)

    return {
        **gst,
        "discount_amount": discount_amount,
        "coupon_code": coupon.code if coupon else None,
        "trial_days": trial_days,
        "original_subtotal": Decimal(str(plan_amount)).quantize(Decimal("0.01")),
    }


def increment_coupon_usage(db: Session, coupon: Coupon | None) -> None:
    if not coupon:
        return
    coupon.used_count += 1
    db.add(coupon)
