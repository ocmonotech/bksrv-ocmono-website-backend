from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.services.commerce_utils import as_utc
from app.models.email_log import EmailLog
from app.models.subscription import Subscription
from app.services.email_service import send_payment_failed_email


def run_subscription_expiry_check(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    expired_count = 0
    dunning_count = 0

    overdue = (
        db.query(Subscription)
        .options(joinedload(Subscription.customer), joinedload(Subscription.plan))
        .filter(Subscription.status.in_(["active", "cancelled", "past_due"]))
        .all()
    )
    overdue = [sub for sub in overdue if as_utc(sub.current_period_end) < now]

    for subscription in overdue:
        if subscription.status in {"active", "past_due"} and subscription.customer:
            already_notified = (
                db.query(EmailLog)
                .filter(
                    EmailLog.template == "payment_failed",
                    EmailLog.reference_type == "subscription",
                    EmailLog.reference_id == subscription.id,
                )
                .first()
            )
            if not already_notified:
                send_payment_failed_email(
                    db,
                    subscription.customer,
                    subscription,
                    subscription.plan.name if subscription.plan else "ClinicPro",
                )
                db.commit()
                dunning_count += 1

        subscription.status = "expired"
        expired_count += 1

    if expired_count:
        db.commit()

    return {"expired": expired_count, "dunning_emails": dunning_count}
