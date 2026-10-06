import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.reminder_service import run_renewal_reminders
from app.services.dunning_service import run_subscription_expiry_check

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinicpro.worker")


def renewal_reminder_job():
    db = SessionLocal()
    try:
        sent = run_renewal_reminders(db)
        logger.info("Renewal reminders sent: %s", sent)
    except Exception:
        logger.exception("Renewal reminder job failed")
    finally:
        db.close()


def subscription_expiry_job():
    db = SessionLocal()
    try:
        result = run_subscription_expiry_check(db)
        logger.info("Subscription expiry check: %s", result)
    except Exception:
        logger.exception("Subscription expiry job failed")
    finally:
        db.close()


def main():
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        renewal_reminder_job,
        CronTrigger(hour=9, minute=0),
        id="renewal_reminders",
        replace_existing=True,
    )

    # Run once on startup so demo/testing works immediately.
    scheduler.add_job(
        subscription_expiry_job,
        CronTrigger(hour=10, minute=0),
        id="subscription_expiry",
        replace_existing=True,
    )

    renewal_reminder_job()
    subscription_expiry_job()

    logger.info("Worker started. Daily renewal reminders at 09:00 IST.")
    scheduler.start()


if __name__ == "__main__":
    main()
