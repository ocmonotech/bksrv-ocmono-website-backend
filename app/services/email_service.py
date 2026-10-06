import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.email_log import EmailLog
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.services.notification_preferences import should_send_email


def _email_provider() -> str:
    return os.getenv("EMAIL_PROVIDER", "mock").lower()


def _email_from() -> str:
    return os.getenv("EMAIL_FROM", "billing@clinicpro.in")


def _site_url() -> str:
    """Public marketing site URL for logos and links in outbound emails."""
    configured = (os.getenv("SITE_URL") or os.getenv("EMAIL_SITE_URL") or "").strip().rstrip("/")
    if configured:
        return configured

    frontend = (os.getenv("FRONTEND_ORIGIN") or os.getenv("NEXT_PUBLIC_SITE_URL") or "").strip().rstrip("/")
    if frontend and "localhost" not in frontend and "127.0.0.1" not in frontend:
        return frontend

    return "https://ocmono.com"


def _logo_url() -> str:
    """Default (light-theme) logo — black mark on light backgrounds."""
    return os.getenv("EMAIL_LOGO_URL") or f"{_site_url()}/assets/img/logo/logo-black.png"


def _logo_url_light() -> str:
    return os.getenv("EMAIL_LOGO_URL_LIGHT") or _logo_url()


def _logo_url_dark() -> str:
    return (
        os.getenv("EMAIL_LOGO_URL_DARK")
        or os.getenv("EMAIL_LOGO_URL_WHITE")
        or f"{_site_url()}/assets/img/logo/logo-white.png"
    )


def wrap_email_html(
    *,
    title: str,
    body_html: str,
    cta_url: str | None = None,
    cta_label: str | None = None,
) -> str:
    """Branded ClinicPro HTML email shell (theme-aware logo, card, optional CTA)."""
    site = _site_url()
    logo_light = _logo_url_light()
    logo_dark = _logo_url_dark()
    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:8px 0 8px;">
                <tr>
                  <td style="border-radius:8px;background:#5B6CFF;">
                    <a href="{cta_url}"
                       style="display:inline-block;padding:12px 20px;font-size:14px;font-weight:600;
                              color:#ffffff;text-decoration:none;border-radius:8px;">
                      {cta_label}
                    </a>
                  </td>
                </tr>
              </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light dark" />
  <meta name="supported-color-schemes" content="light dark" />
  <title>{title}</title>
  <style type="text/css">
    :root {{
      color-scheme: light dark;
    }}
    .cp-email-logo-dark {{
      display: none !important;
      max-height: 0 !important;
      overflow: hidden !important;
      mso-hide: all;
    }}
    .cp-email-body h1, .cp-email-body h2 {{
      margin: 0 0 12px;
      font-size: 22px;
      line-height: 1.3;
      color: #0f172a;
      font-weight: 700;
    }}
    .cp-email-body p {{
      margin: 0 0 12px;
      font-size: 15px;
      line-height: 1.6;
      color: #334155;
    }}
    .cp-email-body a {{
      color: #5B6CFF;
    }}
    .cp-email-body strong {{
      color: #0f172a;
    }}
    @media (prefers-color-scheme: dark) {{
      .cp-email-shell {{
        background: #0B1220 !important;
      }}
      .cp-email-card {{
        background: #111827 !important;
      }}
      .cp-email-header {{
        background: #0B1220 !important;
        border-bottom-color: #1f2937 !important;
      }}
      .cp-email-logo-light {{
        display: none !important;
        max-height: 0 !important;
        overflow: hidden !important;
      }}
      .cp-email-logo-dark {{
        display: block !important;
        max-height: none !important;
        overflow: visible !important;
      }}
      .cp-email-body h1, .cp-email-body h2,
      .cp-email-body strong {{
        color: #f8fafc !important;
      }}
      .cp-email-body p {{
        color: #cbd5e1 !important;
      }}
      .cp-email-footer {{
        color: #94a3b8 !important;
        border-top-color: #1f2937 !important;
      }}
      .cp-email-footer a {{
        color: #cbd5e1 !important;
      }}
    }}
  </style>
  <!--[if mso]>
  <style type="text/css">
    .cp-email-logo-dark {{ display: none !important; }}
  </style>
  <![endif]-->
</head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" class="cp-email-shell" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6fb;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" class="cp-email-card" width="560" cellspacing="0" cellpadding="0"
               style="max-width:560px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;">
          <tr>
            <td class="cp-email-header" style="padding:28px 32px;background:#f8fafc;border-bottom:1px solid #eef0f6;">
              <a href="{site}" style="text-decoration:none;">
                <img class="cp-email-logo-light" src="{logo_light}" alt="ClinicPro" width="200"
                     style="display:block;border:0;outline:none;height:auto;width:200px;max-width:100%;" />
                <img class="cp-email-logo-dark" src="{logo_dark}" alt="ClinicPro" width="200"
                     style="display:none;border:0;outline:none;height:auto;width:200px;max-width:100%;" />
              </a>
            </td>
          </tr>
          <tr>
            <td class="cp-email-body" style="padding:28px 32px 8px;color:#0f172a;">
              {body_html}
              {cta_block}
            </td>
          </tr>
          <tr>
            <td class="cp-email-footer" style="padding:24px 32px 28px;font-size:12px;line-height:1.5;color:#94a3b8;border-top:1px solid #eef0f6;">
              © ClinicPro · <a href="{site}" style="color:#64748b;text-decoration:none;">{site.replace("https://", "").replace("http://", "")}</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _already_sent(db: Session, *, template: str, reference_type: str, reference_id: int) -> bool:
    existing = (
        db.query(EmailLog)
        .filter(
            EmailLog.template == template,
            EmailLog.reference_type == reference_type,
            EmailLog.reference_id == reference_id,
            EmailLog.status.in_(["sent", "mock"]),
        )
        .first()
    )
    return existing is not None


def _log_email(
    db: Session,
    *,
    customer_id: int | None,
    template: str,
    recipient: str,
    subject: str,
    status: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
    error_message: str | None = None,
) -> EmailLog:
    entry = EmailLog(
        customer_id=customer_id,
        template=template,
        recipient=recipient,
        subject=subject,
        status=status,
        reference_type=reference_type,
        reference_id=reference_id,
        error_message=error_message,
        sent_at=datetime.now(timezone.utc) if status in {"sent", "mock"} else None,
    )
    db.add(entry)
    db.flush()
    return entry


def _send_via_smtp(*, recipient: str, subject: str, html_body: str, attachment_path: Path | None = None) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    # Gmail app passwords are often shown with spaces; strip them for SMTP auth.
    password = (os.getenv("SMTP_PASSWORD") or "").replace(" ", "")

    if not host or not user or not password:
        raise RuntimeError("SMTP is not fully configured")

    message = MIMEMultipart()
    message["From"] = _email_from()
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    if attachment_path and attachment_path.exists():
        with attachment_path.open("rb") as handle:
            part = MIMEApplication(handle.read(), Name=attachment_path.name)
        part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
        message.attach(part)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(_email_from(), [recipient], message.as_string())


def send_email(
    db: Session,
    *,
    customer_id: int | None,
    template: str,
    recipient: str,
    subject: str,
    html_body: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
    attachment_path: Path | None = None,
) -> EmailLog:
    provider = _email_provider()

    if provider == "mock":
        print(f"[EMAIL:mock] To={recipient} Subject={subject}")
        return _log_email(
            db,
            customer_id=customer_id,
            template=template,
            recipient=recipient,
            subject=subject,
            status="mock",
            reference_type=reference_type,
            reference_id=reference_id,
        )

    try:
        if provider == "smtp":
            _send_via_smtp(
                recipient=recipient,
                subject=subject,
                html_body=html_body,
                attachment_path=attachment_path,
            )
        else:
            print(f"[EMAIL:console] To={recipient}\nSubject={subject}\n{html_body[:500]}")
        return _log_email(
            db,
            customer_id=customer_id,
            template=template,
            recipient=recipient,
            subject=subject,
            status="sent" if provider == "smtp" else "mock",
            reference_type=reference_type,
            reference_id=reference_id,
        )
    except Exception as exc:
        return _log_email(
            db,
            customer_id=customer_id,
            template=template,
            recipient=recipient,
            subject=subject,
            status="failed",
            reference_type=reference_type,
            reference_id=reference_id,
            error_message=str(exc),
        )


def send_welcome_email(db: Session, customer: Customer, subscription: Subscription, plan_name: str) -> None:
    if not should_send_email(customer, "welcome"):
        return
    if _already_sent(db, template="welcome", reference_type="subscription", reference_id=subscription.id):
        return

    html = wrap_email_html(
        title=f"Welcome to ClinicPro {plan_name}",
        body_html=f"""
    <h2>Welcome to ClinicPro, {customer.name}!</h2>
    <p>Your <strong>{plan_name}</strong> subscription is now active.</p>
    <p>Billing portal: sign in with <strong>{customer.email}</strong> to view invoices and manage your plan.</p>
        """,
        cta_url=_site_url(),
        cta_label="Visit ClinicPro",
    )
    send_email(
        db,
        customer_id=customer.id,
        template="welcome",
        recipient=customer.email,
        subject=f"Welcome to ClinicPro {plan_name}",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_payment_receipt_email(
    db: Session,
    customer: Customer,
    payment: Payment,
    plan_name: str,
    uploads_root: Path,
    *,
    force: bool = False,
) -> None:
    if not should_send_email(customer, "payment_receipt"):
        return
    if not force and _already_sent(db, template="payment_receipt", reference_type="payment", reference_id=payment.id):
        return

    attachment = None
    if payment.pdf_path:
        attachment = uploads_root / payment.pdf_path.replace("invoices/", "invoices/")

    html = wrap_email_html(
        title="Payment received",
        body_html=f"""
    <h2>Payment received</h2>
    <p>Hi {customer.name},</p>
    <p>We received your payment of <strong>₹ {payment.total}</strong> for ClinicPro {plan_name}.</p>
    <p>Invoice number: <strong>{payment.invoice_number}</strong></p>
        """,
    )
    send_email(
        db,
        customer_id=customer.id,
        template="payment_receipt",
        recipient=customer.email,
        subject=f"ClinicPro payment receipt — {payment.invoice_number}",
        html_body=html,
        reference_type="payment",
        reference_id=payment.id,
        attachment_path=attachment,
    )


def send_renewal_reminder_email(
    db: Session,
    customer: Customer,
    subscription: Subscription,
    plan_name: str,
) -> None:
    if not should_send_email(customer, "renewal_reminder"):
        return
    if _already_sent(db, template="renewal_reminder", reference_type="subscription", reference_id=subscription.id):
        return

    renew_date = subscription.current_period_end.strftime("%d %b %Y")
    html = wrap_email_html(
        title=f"ClinicPro renews on {renew_date}",
        body_html=f"""
    <h2>Subscription renewal reminder</h2>
    <p>Hi {customer.name},</p>
    <p>Your ClinicPro <strong>{plan_name}</strong> plan will renew on <strong>{renew_date}</strong>.</p>
    <p>No action is needed if your payment method is active.</p>
        """,
    )
    send_email(
        db,
        customer_id=customer.id,
        template="renewal_reminder",
        recipient=customer.email,
        subject=f"ClinicPro renews on {renew_date}",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_cancellation_email(
    db: Session,
    customer: Customer,
    subscription: Subscription,
    plan_name: str,
) -> None:
    if not should_send_email(customer, "subscription_cancelled"):
        return
    end_date = subscription.current_period_end.strftime("%d %b %Y")
    html = wrap_email_html(
        title="ClinicPro subscription cancelled",
        body_html=f"""
    <h2>Subscription cancelled</h2>
    <p>Hi {customer.name},</p>
    <p>Your ClinicPro <strong>{plan_name}</strong> subscription has been cancelled.</p>
    <p>You will retain access until <strong>{end_date}</strong>.</p>
        """,
    )
    send_email(
        db,
        customer_id=customer.id,
        template="subscription_cancelled",
        recipient=customer.email,
        subject="ClinicPro subscription cancelled",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_plan_change_email(
    db: Session,
    customer: Customer,
    subscription: Subscription,
    old_plan_name: str,
    new_plan_name: str,
) -> None:
    if not should_send_email(customer, "plan_changed"):
        return
    html = wrap_email_html(
        title=f"ClinicPro plan changed to {new_plan_name}",
        body_html=f"""
    <h2>Plan updated</h2>
    <p>Hi {customer.name},</p>
    <p>Your ClinicPro plan has been changed from <strong>{old_plan_name}</strong> to <strong>{new_plan_name}</strong>.</p>
        """,
    )
    send_email(
        db,
        customer_id=customer.id,
        template="plan_changed",
        recipient=customer.email,
        subject=f"ClinicPro plan changed to {new_plan_name}",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_reactivation_email(
    db: Session,
    customer: Customer,
    subscription: Subscription,
    plan_name: str,
) -> None:
    if not should_send_email(customer, "subscription_reactivated"):
        return
    html = wrap_email_html(
        title="ClinicPro subscription reactivated",
        body_html=f"""
    <h2>Welcome back to ClinicPro</h2>
    <p>Hi {customer.name},</p>
    <p>Your <strong>{plan_name}</strong> subscription has been reactivated.</p>
    <p>Your next renewal date is <strong>{subscription.current_period_end.strftime('%d %b %Y')}</strong>.</p>
        """,
    )
    send_email(
        db,
        customer_id=customer.id,
        template="subscription_reactivated",
        recipient=customer.email,
        subject="ClinicPro subscription reactivated",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_resubscribe_email(
    db: Session,
    customer: Customer,
    subscription: Subscription,
    plan_name: str,
) -> None:
    if not should_send_email(customer, "subscription_resubscribed"):
        return
    html = wrap_email_html(
        title=f"ClinicPro {plan_name} subscription active",
        body_html=f"""
    <h2>Subscription renewed</h2>
    <p>Hi {customer.name},</p>
    <p>Your ClinicPro <strong>{plan_name}</strong> subscription is active again.</p>
    <p>Renews on <strong>{subscription.current_period_end.strftime('%d %b %Y')}</strong>.</p>
        """,
    )
    send_email(
        db,
        customer_id=customer.id,
        template="subscription_resubscribed",
        recipient=customer.email,
        subject=f"ClinicPro {plan_name} subscription active",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_payment_failed_email(
    db: Session,
    customer: Customer,
    subscription: Subscription,
    plan_name: str,
) -> None:
    if not should_send_email(customer, "payment_failed"):
        return
    html = wrap_email_html(
        title="Action required: ClinicPro payment failed",
        body_html=f"""
    <h2>Payment required</h2>
    <p>Hi {customer.name},</p>
    <p>We could not renew your ClinicPro <strong>{plan_name}</strong> subscription.</p>
    <p>Please sign in to your billing account and update your payment method to avoid interruption.</p>
        """,
        cta_url=os.getenv("NEXT_PUBLIC_ACCOUNTS_URL") or "https://accounts.clinicpro.cc",
        cta_label="Update payment method",
    )
    send_email(
        db,
        customer_id=customer.id,
        template="payment_failed",
        recipient=customer.email,
        subject="Action required: ClinicPro payment failed",
        html_body=html,
        reference_type="subscription",
        reference_id=subscription.id,
    )


def send_demo_booking_confirmation(
    db: Session,
    *,
    submission_id: int,
    name: str,
    email: str,
    demo_date: str,
    demo_time: str,
) -> None:
    html = wrap_email_html(
        title="ClinicPro — demo request received",
        body_html=f"""
    <h2>Your ClinicPro demo is requested</h2>
    <p>Hi {name},</p>
    <p>Thank you for booking a demo with ClinicPro.</p>
    <p><strong>Preferred slot:</strong> {demo_date} at {demo_time}</p>
    <p>Our team will confirm your session within 24 hours.</p>
        """,
        cta_url=_site_url(),
        cta_label="Visit ClinicPro",
    )
    send_email(
        db,
        customer_id=None,
        template="demo_booking_confirmation",
        recipient=email,
        subject="ClinicPro — demo request received",
        html_body=html,
        reference_type="contact",
        reference_id=submission_id,
    )


def send_contact_auto_reply(db: Session, *, submission_id: int, name: str, email: str) -> None:
    html = wrap_email_html(
        title="ClinicPro — we received your request",
        body_html=f"""
    <h2>We received your message</h2>
    <p>Hi {name},</p>
    <p>Thank you for contacting ClinicPro. Our team will respond within one business day.</p>
        """,
        cta_url=_site_url(),
        cta_label="Visit ClinicPro",
    )
    send_email(
        db,
        customer_id=None,
        template="contact_auto_reply",
        recipient=email,
        subject="ClinicPro — we received your request",
        html_body=html,
        reference_type="contact",
        reference_id=submission_id,
    )


def send_contact_admin_notification(
    db: Session,
    *,
    submission_id: int,
    full_name: str,
    email: str,
    phone: str,
    clinic_name: str,
    inquiry_type: str,
    message: str,
) -> None:
    admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL", os.getenv("EMAIL_FROM", "billing@clinicpro.in"))
    html = wrap_email_html(
        title=f"New contact: {inquiry_type} — {clinic_name}",
        body_html=f"""
    <h2>New contact form submission</h2>
    <p><strong>Name:</strong> {full_name}</p>
    <p><strong>Email:</strong> {email}</p>
    <p><strong>Phone:</strong> {phone}</p>
    <p><strong>Clinic:</strong> {clinic_name}</p>
    <p><strong>Inquiry:</strong> {inquiry_type}</p>
    <p><strong>Message:</strong><br>{message}</p>
        """,
    )
    send_email(
        db,
        customer_id=None,
        template="contact_admin",
        recipient=admin_email,
        subject=f"New contact: {inquiry_type} — {clinic_name}",
        html_body=html,
        reference_type="contact",
        reference_id=submission_id,
    )


def send_commerce_admin_notification(
    db: Session,
    *,
    order_number: str,
    order_type: str,
    customer_name: str,
    customer_email: str,
    plan_name: str,
    total,
    invoice_number: str | None = None,
    order_id: int | None = None,
) -> None:
    admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL", os.getenv("EMAIL_FROM", "billing@clinicpro.in"))
    html = wrap_email_html(
        title=f"New order {order_number} — ₹ {total}",
        body_html=f"""
    <h2>New paid order — ClinicPro</h2>
    <p><strong>Order:</strong> {order_number}</p>
    <p><strong>Type:</strong> {order_type}</p>
    <p><strong>Customer:</strong> {customer_name} ({customer_email})</p>
    <p><strong>Plan:</strong> {plan_name}</p>
    <p><strong>Total:</strong> ₹ {total}</p>
    <p><strong>Invoice:</strong> {invoice_number or "Pending"}</p>
        """,
    )
    send_email(
        db,
        customer_id=None,
        template="commerce_admin",
        recipient=admin_email,
        subject=f"New order {order_number} — ₹ {total}",
        html_body=html,
        reference_type="order",
        reference_id=order_id,
    )


def send_newsletter_subscribe_confirmation(
    db: Session,
    *,
    subscriber_id: int,
    email: str,
) -> None:
    html = wrap_email_html(
        title="ClinicPro — you're subscribed to our newsletter",
        body_html="""
    <h2>You're subscribed to the ClinicPro newsletter</h2>
    <p>Thank you for subscribing.</p>
    <p>You'll receive our latest news, healthcare insights, product updates, and practical tips for running your clinic.</p>
    <p style="color:#64748b;font-size:14px;">If you did not sign up, you can ignore this email.</p>
        """,
        cta_url=_site_url(),
        cta_label="Visit ClinicPro",
    )
    send_email(
        db,
        customer_id=None,
        template="newsletter_subscribe",
        recipient=email,
        subject="ClinicPro — you're subscribed to our newsletter",
        html_body=html,
        reference_type="newsletter",
        reference_id=subscriber_id,
    )


def send_password_reset_email(db: Session, customer: Customer, reset_url: str) -> None:
    html = wrap_email_html(
        title="Reset your ClinicPro password",
        body_html=f"""
    <h2>Reset your ClinicPro password</h2>
    <p>Hi {customer.name},</p>
    <p>We received a request to reset the password for your billing account (<strong>{customer.email}</strong>).</p>
    <p style="color:#64748b;font-size:14px;">This link expires in 60 minutes. If you did not request this, you can ignore this email.</p>
        """,
        cta_url=reset_url,
        cta_label="Choose a new password",
    )
    send_email(
        db,
        customer_id=customer.id,
        template="password_reset",
        recipient=customer.email,
        subject="Reset your ClinicPro password",
        html_body=html,
        reference_type="customer",
        reference_id=customer.id,
    )
    print(f"[PASSWORD_RESET] Reset link for {customer.email}: {reset_url}")
