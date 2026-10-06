import hashlib
import hmac
import os
import uuid
from decimal import Decimal

import requests


def get_payment_mode() -> str:
    mode = os.getenv("PAYMENT_MODE", "mock").lower()
    if mode == "razorpay" and os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET"):
        return "razorpay"
    return "mock"


def get_razorpay_key_id() -> str | None:
    return os.getenv("RAZORPAY_KEY_ID")


def _auth() -> tuple[str, str]:
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay credentials are not configured")
    return key_id, key_secret


def create_gateway_order(*, order_number: str, total: Decimal, customer_email: str, customer_phone: str) -> dict:
    amount_paise = int(total * 100)
    if get_payment_mode() == "mock" or amount_paise <= 0:
        return {
            "gateway_order_id": f"mock_order_{uuid.uuid4().hex[:12]}",
            "razorpay_key_id": None,
            "amount_paise": max(amount_paise, 0),
        }

    key_id, key_secret = _auth()
    response = requests.post(
        "https://api.razorpay.com/v1/orders",
        auth=(key_id, key_secret),
        json={
            "amount": int(total * 100),
            "currency": "INR",
            "receipt": order_number,
            "notes": {
                "customer_email": customer_email,
                "customer_phone": customer_phone,
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    gateway_order = response.json()
    return {
        "gateway_order_id": gateway_order["id"],
        "razorpay_key_id": key_id,
        "amount_paise": gateway_order["amount"],
    }


def verify_razorpay_payment(*, gateway_order_id: str, gateway_payment_id: str, signature: str) -> bool:
    if get_payment_mode() == "mock":
        return True

    _, key_secret = _auth()
    payload = f"{gateway_order_id}|{gateway_payment_id}".encode()
    expected = hmac.new(key_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    if not secret:
        return False

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_razorpay_plan_id(plan_slug: str, billing_interval: str) -> str | None:
    env_key = f"RAZORPAY_PLAN_{plan_slug.upper().replace('-', '_')}_{billing_interval.upper()}"
    return os.getenv(env_key) or None


def create_razorpay_subscription(
    *,
    razorpay_plan_id: str,
    customer_email: str,
    customer_name: str,
    customer_phone: str,
    total_count: int = 120,
) -> dict:
    if get_payment_mode() == "mock":
        return {"id": f"mock_sub_{uuid.uuid4().hex[:12]}"}

    key_id, key_secret = _auth()
    response = requests.post(
        "https://api.razorpay.com/v1/subscriptions",
        auth=(key_id, key_secret),
        json={
            "plan_id": razorpay_plan_id,
            "total_count": total_count,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "customer_email": customer_email,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
