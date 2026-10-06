import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.subscription import Subscription
from app.services.email_service import send_payment_failed_email
from app.services.order_fulfillment import fulfill_paid_order
from app.services.payment_gateway import verify_webhook_signature
from app.services.renewal_service import find_subscription_for_renewal, renew_subscription
from app.services.sms_service import send_sms

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.head.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    payload = json.loads(body.decode())
    event = payload.get("event", "")

    if event == "payment.captured":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        gateway_order_id = payment_entity.get("order_id")
        gateway_payment_id = payment_entity.get("id")

        if not gateway_order_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing order id")

        order = db.query(Order).filter(Order.gateway_order_id == gateway_order_id).first()
        if not order:
            return {"status": "ignored", "reason": "order not found"}

        fulfill_paid_order(db, order=order, gateway_payment_id=gateway_payment_id)
        return {"status": "ok", "event": event, "order_id": order.id}

    if event == "subscription.charged":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        subscription_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        gateway_payment_id = payment_entity.get("id")
        gateway_subscription_id = subscription_entity.get("id")
        customer_email = payment_entity.get("email")

        subscription = find_subscription_for_renewal(
            db,
            gateway_subscription_id=gateway_subscription_id,
            customer_email=customer_email,
        )
        if not subscription:
            return {"status": "ignored", "reason": "subscription not found"}

        payment = renew_subscription(db, subscription=subscription, gateway_payment_id=gateway_payment_id)
        return {"status": "ok", "event": event, "payment_id": payment.id}

    if event in {"subscription.cancelled", "subscription.completed", "subscription.halted"}:
        subscription_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        gateway_subscription_id = subscription_entity.get("id")
        if not gateway_subscription_id:
            return {"status": "ignored", "reason": "missing subscription id"}

        subscription = (
            db.query(Subscription)
            .filter(Subscription.gateway_subscription_id == gateway_subscription_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
        if not subscription:
            return {"status": "ignored", "reason": "subscription not found"}

        if event == "subscription.cancelled":
            subscription.status = "cancelled"
            subscription.cancelled_at = datetime.now(timezone.utc)
        else:
            subscription.status = "expired" if event == "subscription.completed" else "past_due"
        db.commit()
        return {"status": "ok", "event": event, "subscription_id": subscription.id}

    if event == "payment.failed":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        customer_email = payment_entity.get("email")
        customer = db.query(Customer).filter(Customer.email == (customer_email or "").lower()).first()
        if customer:
            subscription = (
                db.query(Subscription)
                .options(joinedload(Subscription.plan))
                .filter(Subscription.customer_id == customer.id)
                .order_by(Subscription.created_at.desc())
                .first()
            )
            if subscription:
                subscription.status = "past_due"
                db.commit()
                send_payment_failed_email(db, customer, subscription, subscription.plan.name if subscription.plan else "ClinicPro")
                if customer.phone:
                    send_sms(
                        db,
                        phone=customer.phone,
                        message="ClinicPro payment failed. Please update your billing details to avoid service interruption.",
                        template="payment_failed",
                        customer_id=customer.id,
                        customer=customer,
                        reference_type="subscription",
                        reference_id=subscription.id,
                    )
                db.commit()
        return {"status": "ok", "event": event}

    return {"status": "ignored", "event": event}
