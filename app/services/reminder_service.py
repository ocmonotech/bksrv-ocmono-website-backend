from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.services.commerce_utils import as_utc
from app.models.email_log import EmailLog
from app.models.subscription import Subscription
from app.services.email_service import send_renewal_reminder_email


def run_renewal_reminders(db: Session, *, days_before: int = 3) -> int:
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(days=days_before - 1)
    window_end = now + timedelta(days=days_before + 1)

    subscriptions = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.customer))
        .filter(Subscription.status == "active")
        .all()
    )
    subscriptions = [
        sub
        for sub in subscriptions
        if window_start <= as_utc(sub.current_period_end) <= window_end
    ]

    sent_count = 0
    for subscription in subscriptions:
        if not subscription.customer or not subscription.plan:
            continue

        before_count = (
            db.query(EmailLog)
            .filter(
                EmailLog.template == "renewal_reminder",
                EmailLog.reference_type == "subscription",
                EmailLog.reference_id == subscription.id,
            )
            .count()
        )
        send_renewal_reminder_email(db, subscription.customer, subscription, subscription.plan.name)
        if subscription.customer.phone:
            from app.services.sms_service import send_sms

            send_sms(
                db,
                phone=subscription.customer.phone,
                message=f"Reminder: ClinicPro {subscription.plan.name} renews on {subscription.current_period_end.strftime('%d %b %Y')}.",
                template="renewal_reminder",
                customer_id=subscription.customer.id,
                customer=subscription.customer,
                reference_type="subscription",
                reference_id=subscription.id,
            )
        db.commit()

        after_count = (
            db.query(EmailLog)
            .filter(
                EmailLog.template == "renewal_reminder",
                EmailLog.reference_type == "subscription",
                EmailLog.reference_id == subscription.id,
            )
            .count()
        )
        if after_count > before_count:
            sent_count += 1

    return sent_count
