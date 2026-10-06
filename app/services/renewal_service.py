import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.services.commerce_utils import generate_invoice_number, generate_order_number, get_company_state
from app.services.email_service import send_commerce_admin_notification, send_payment_receipt_email
from app.services.gst import calculate_gst
from app.services.invoice_pdf import generate_invoice_pdf
from app.services.sms_service import send_sms


def renew_subscription(
    db: Session,
    *,
    subscription: Subscription,
    gateway_payment_id: str | None = None,
    order: Order | None = None,
) -> Payment:
    customer = db.query(Customer).filter(Customer.id == subscription.customer_id).first()
    plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
    plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first()

    now = datetime.now(timezone.utc)
    period_days = 365 if subscription.billing_interval == "yearly" else 30

    gst = calculate_gst(plan_price.amount, customer.state, get_company_state())

    if order:
        order.status = "paid"
        order.subtotal = gst["subtotal"]
        order.cgst = gst["cgst"]
        order.sgst = gst["sgst"]
        order.igst = gst["igst"]
        order.gst_total = gst["gst_total"]
        order.total = gst["total"]
        if gateway_payment_id:
            order.gateway_order_id = gateway_payment_id
        db.flush()
    else:
        order = Order(
            order_number=generate_order_number(db),
            customer_id=customer.id,
            plan_price_id=plan_price.id,
            status="paid",
            subtotal=gst["subtotal"],
            cgst=gst["cgst"],
            sgst=gst["sgst"],
            igst=gst["igst"],
            gst_total=gst["gst_total"],
            total=gst["total"],
            discount_amount=0,
            gateway_order_id=gateway_payment_id or f"renew_{uuid.uuid4().hex[:12]}",
            order_type="renewal",
            subscription_id=subscription.id,
        )
        db.add(order)
        db.flush()

    payment = Payment(
        invoice_number=generate_invoice_number(db),
        order_id=order.id,
        customer_id=customer.id,
        subscription_id=subscription.id,
        subtotal=gst["subtotal"],
        cgst=gst["cgst"],
        sgst=gst["sgst"],
        igst=gst["igst"],
        gst_total=gst["gst_total"],
        total=gst["total"],
        status="paid",
        payment_method="razorpay" if gateway_payment_id else "mock",
        gateway_payment_id=gateway_payment_id or f"renew_{uuid.uuid4().hex[:12]}",
        paid_at=now,
    )

    subscription.status = "active"
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=period_days)
    subscription.cancelled_at = None

    db.add(payment)
    db.flush()

    payment.pdf_path = generate_invoice_pdf(
        payment=payment,
        customer=customer,
        plan=plan,
        billing_interval=subscription.billing_interval,
    )
    db.commit()
    db.refresh(payment)

    uploads_root = __import__("pathlib").Path(__file__).resolve().parents[2] / "uploads"
    send_payment_receipt_email(db, customer, payment, plan.name, uploads_root)
    if customer.phone:
        send_sms(
            db,
            phone=customer.phone,
            message=f"ClinicPro renewed. Invoice {payment.invoice_number}. Amount ₹ {payment.total}.",
            template="renewal_success",
            customer_id=customer.id,
            customer=customer,
            reference_type="payment",
            reference_id=payment.id,
        )
    send_commerce_admin_notification(
        db,
        order_number=order.order_number,
        order_type=order.order_type or "renewal",
        customer_name=customer.name,
        customer_email=customer.email,
        plan_name=plan.name,
        total=order.total,
        invoice_number=payment.invoice_number,
        order_id=order.id,
    )
    db.commit()
    return payment


def find_subscription_for_renewal(db: Session, *, gateway_subscription_id: str | None, customer_email: str | None) -> Subscription | None:
    query = db.query(Subscription).options(joinedload(Subscription.customer))
    if gateway_subscription_id:
        sub = query.filter(Subscription.gateway_subscription_id == gateway_subscription_id).first()
        if sub:
            return sub
    if customer_email:
        customer = db.query(Customer).filter(Customer.email == customer_email.lower()).first()
        if customer:
            return (
                query.filter(Subscription.customer_id == customer.id, Subscription.status.in_(["active", "cancelled", "past_due"]))
                .order_by(Subscription.created_at.desc())
                .first()
            )
    return None
