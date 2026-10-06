import os
from datetime import datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models.payment import Payment


def get_company_state() -> str:
    return os.getenv("COMPANY_STATE", "Maharashtra")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_company_gstin() -> str:
    return os.getenv("COMPANY_GSTIN", "27AABCU9603R1ZM")


def get_company_legal_name() -> str:
    return os.getenv("COMPANY_LEGAL_NAME", "ClinicPro Technologies Pvt Ltd")


from app.models.order import Order
from app.models.credit_note import CreditNote


def generate_order_number(db: Session) -> str:
    count = db.query(Order).count()
    year = datetime.now(timezone.utc).year
    return f"ORD-{year}-{count + 1:05d}"


def generate_invoice_number(db: Session) -> str:
    count = db.query(Payment).count()
    now = datetime.now(timezone.utc)
    fy_start = now.year if now.month >= 4 else now.year - 1
    fy_end = fy_start + 1
    fy_label = f"{fy_start}-{str(fy_end)[-2:]}"
    return f"CP/{fy_label}/{count + 1:05d}"


def generate_credit_note_number(db: Session) -> str:
    count = db.query(CreditNote).count()
    now = datetime.now(timezone.utc)
    fy_start = now.year if now.month >= 4 else now.year - 1
    fy_end = fy_start + 1
    fy_label = f"{fy_start}-{str(fy_end)[-2:]}"
    return f"CN/{fy_label}/{count + 1:05d}"


def migrate_commerce_columns():
    inspector = inspect(engine)

    if inspector.has_table("payments"):
        columns = {column["name"] for column in inspector.get_columns("payments")}
        with engine.begin() as connection:
            if "pdf_path" not in columns:
                connection.execute(text("ALTER TABLE payments ADD COLUMN pdf_path VARCHAR(500) NULL"))

    if inspector.has_table("orders"):
        columns = {column["name"] for column in inspector.get_columns("orders")}
        with engine.begin() as connection:
            if "coupon_code" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN coupon_code VARCHAR(30) NULL"))
            if "discount_amount" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0"))
            if "trial_days" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN trial_days INT NULL"))
            if "order_type" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN order_type VARCHAR(20) NOT NULL DEFAULT 'checkout'"))
            if "subscription_id" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN subscription_id INT NULL"))
                connection.execute(text("ALTER TABLE orders ADD INDEX idx_orders_subscription_id (subscription_id)"))
            if "clinic_name" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN clinic_name VARCHAR(180) NULL"))
            if "addons_json" not in columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN addons_json VARCHAR(2000) NULL"))

    if inspector.has_table("customers"):
        columns = {column["name"] for column in inspector.get_columns("customers")}
        with engine.begin() as connection:
            if "notify_email_billing" not in columns:
                connection.execute(text("ALTER TABLE customers ADD COLUMN notify_email_billing TINYINT(1) NOT NULL DEFAULT 1"))
            if "notify_email_marketing" not in columns:
                connection.execute(text("ALTER TABLE customers ADD COLUMN notify_email_marketing TINYINT(1) NOT NULL DEFAULT 0"))
            if "notify_sms_billing" not in columns:
                connection.execute(text("ALTER TABLE customers ADD COLUMN notify_sms_billing TINYINT(1) NOT NULL DEFAULT 1"))

    if inspector.has_table("subscriptions"):
        columns = {column["name"] for column in inspector.get_columns("subscriptions")}
        with engine.begin() as connection:
            if "clinic_name" not in columns:
                connection.execute(text("ALTER TABLE subscriptions ADD COLUMN clinic_name VARCHAR(180) NULL"))
                connection.execute(
                    text(
                        """
                        UPDATE subscriptions s
                        JOIN customers c ON c.id = s.customer_id
                        SET s.clinic_name = c.clinic_name
                        WHERE s.clinic_name IS NULL AND c.clinic_name IS NOT NULL
                        """
                    )
                )
