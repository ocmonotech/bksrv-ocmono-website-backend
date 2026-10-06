from app.models.customer import Customer

BILLING_EMAIL_TEMPLATES = {
    "welcome",
    "payment_receipt",
    "renewal_reminder",
    "subscription_cancelled",
    "plan_changed",
    "subscription_reactivated",
    "subscription_resubscribed",
    "payment_failed",
}

BILLING_SMS_TEMPLATES = {
    "payment_success",
    "renewal_success",
    "resubscribe_success",
    "renewal_reminder",
    "payment_failed",
    "plan_change",
}


def wants_billing_email(customer: Customer | None) -> bool:
    if not customer:
        return True
    return getattr(customer, "notify_email_billing", True)


def wants_marketing_email(customer: Customer | None) -> bool:
    if not customer:
        return True
    return getattr(customer, "notify_email_marketing", False)


def wants_billing_sms(customer: Customer | None) -> bool:
    if not customer:
        return True
    return getattr(customer, "notify_sms_billing", True)


def should_send_email(customer: Customer | None, template: str) -> bool:
    if template in BILLING_EMAIL_TEMPLATES:
        return wants_billing_email(customer)
    return True
