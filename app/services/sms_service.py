import os

import requests
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.email_log import EmailLog
from app.services.notification_preferences import BILLING_SMS_TEMPLATES, wants_billing_sms


def _sms_provider() -> str:
    return os.getenv("SMS_PROVIDER", "mock").lower()


def send_sms(
    db: Session,
    *,
    phone: str,
    message: str,
    template: str,
    customer_id: int | None = None,
    customer: Customer | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> None:
    if customer and template in BILLING_SMS_TEMPLATES and not wants_billing_sms(customer):
        return

    provider = _sms_provider()
    recipient = phone.strip()

    if provider == "mock":
        print(f"[SMS:mock] To={recipient} Message={message[:120]}")
        status = "mock"
    elif provider == "msg91":
        auth_key = os.getenv("MSG91_AUTH_KEY")
        sender_id = os.getenv("MSG91_SENDER_ID", "CLINIC")
        if not auth_key:
            raise RuntimeError("MSG91_AUTH_KEY is not configured")
        response = requests.post(
            "https://api.msg91.com/api/v5/flow/",
            headers={"authkey": auth_key, "Content-Type": "application/json"},
            json={
                "template_id": os.getenv("MSG91_TEMPLATE_ID", ""),
                "short_url": "0",
                "recipients": [{"mobiles": recipient.replace("+", ""), "message": message, "sender": sender_id}],
            },
            timeout=30,
        )
        response.raise_for_status()
        status = "sent"
    else:
        print(f"[SMS:console] To={recipient} Message={message}")
        status = "mock"

    db.add(
        EmailLog(
            customer_id=customer_id,
            template=f"sms_{template}",
            recipient=recipient,
            subject=message[:255],
            status=status,
            reference_type=reference_type,
            reference_id=reference_id,
        )
    )
