import os

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.services.customer_auth import (
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.services.email_service import send_password_reset_email

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")


def request_password_reset(db: Session, *, email: str) -> None:
    customer = (
        db.query(Customer)
        .filter(Customer.email == email.lower(), Customer.is_active.is_(True))
        .first()
    )
    if not customer:
        return

    token = create_password_reset_token(customer.id, customer.email)
    reset_url = f"{FRONTEND_ORIGIN.rstrip('/')}/reset-password?token={token}"
    send_password_reset_email(db, customer, reset_url)
    db.commit()


def reset_password_with_token(db: Session, *, token: str, new_password: str) -> Customer:
    try:
        payload = decode_password_reset_token(token)
    except Exception as exc:
        raise ValueError("Invalid or expired reset link. Please request a new one.") from exc

    customer_id = int(payload["sub"])
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.is_active.is_(True)).first()
    if not customer or customer.email.lower() != str(payload.get("email", "")).lower():
        raise ValueError("Invalid or expired reset link. Please request a new one.")

    customer.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(customer)
    return customer


def change_customer_password(
    db: Session,
    *,
    customer: Customer,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, customer.password_hash):
        raise ValueError("Current password is incorrect.")

    if verify_password(new_password, customer.password_hash):
        raise ValueError("New password must be different from your current password.")

    customer.password_hash = hash_password(new_password)
    db.commit()
