from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.coupon import Coupon
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.services.customer_auth import hash_password
from app.services.commerce_utils import (
    generate_invoice_number,
    generate_order_number,
    get_company_state,
)
from app.services.gst import calculate_gst

PLAN_SEED = [
    {
        "slug": "starter",
        "name": "Starter",
        "description": "Perfect for individual practitioners getting started.",
        "features": [
            "Clinic website included",
            "Smart calendar & appointments",
            "Digital prescriptions & billing",
            "1 staff user",
        ],
        "is_popular": False,
        "sort_order": 1,
        "prices": {"monthly": Decimal("599.00"), "yearly": Decimal("5990.00")},
    },
    {
        "slug": "professional",
        "name": "Professional",
        "description": "Ideal for growing multi-practitioner clinics.",
        "features": [
            "Everything in Starter",
            "Revenue dashboard & CRM",
            "Treatment operations suite",
            "Practitioner scheduling",
        ],
        "is_popular": True,
        "sort_order": 2,
        "prices": {"monthly": Decimal("1299.00"), "yearly": Decimal("12990.00")},
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "description": "For large clinics and healthcare networks.",
        "features": [
            "Everything in Professional",
            "Dedicated account manager",
            "Priority support (2–6 hours)",
            "5 users per role",
        ],
        "is_popular": False,
        "sort_order": 3,
        "prices": {"monthly": Decimal("2299.00"), "yearly": Decimal("22990.00")},
    },
]

DEMO_CUSTOMER = {
    "email": "demo@clinicpro.in",
    "password": "demo123456",
    "name": "Dr. Priya Sharma",
    "phone": "+91 98765 43210",
    "clinic_name": "Sharma Family Clinic",
    "gstin": "27AABCU9603R1ZM",
    "billing_address": "101, Linking Road, Bandra West",
    "state": "Maharashtra",
    "city": "Mumbai",
    "pincode": "400050",
}


def seed_commerce(db: Session):
    _seed_plans(db)
    _seed_coupons(db)
    _seed_demo_customer(db)


def _seed_plans(db: Session):
    if db.query(Plan).count() > 0:
        return

    for item in PLAN_SEED:
        plan = Plan(
            slug=item["slug"],
            name=item["name"],
            description=item["description"],
            features=item["features"],
            is_popular=item["is_popular"],
            sort_order=item["sort_order"],
            is_active=True,
        )
        db.add(plan)
        db.flush()

        for interval, amount in item["prices"].items():
            db.add(
                PlanPrice(
                    plan_id=plan.id,
                    billing_interval=interval,
                    amount=amount,
                    currency="INR",
                    is_active=True,
                )
            )

    db.commit()


COUPON_SEED = [
    {
        "code": "WELCOME10",
        "description": "10% off your first subscription",
        "discount_type": "percent",
        "discount_value": Decimal("10.00"),
        "billing_interval": None,
        "trial_days": None,
        "max_uses": 1000,
    },
    {
        "code": "ANNUAL20",
        "description": "20% off annual plans",
        "discount_type": "percent",
        "discount_value": Decimal("20.00"),
        "billing_interval": "yearly",
        "trial_days": None,
        "max_uses": None,
    },
    {
        "code": "TRIAL14",
        "description": "14-day free trial on monthly plans",
        "discount_type": "percent",
        "discount_value": Decimal("100.00"),
        "billing_interval": "monthly",
        "trial_days": 14,
        "max_uses": None,
    },
]


def _seed_coupons(db: Session):
    if db.query(Coupon).count() > 0:
        return

    for item in COUPON_SEED:
        db.add(
            Coupon(
                code=item["code"],
                description=item["description"],
                discount_type=item["discount_type"],
                discount_value=item["discount_value"],
                billing_interval=item["billing_interval"],
                trial_days=item["trial_days"],
                max_uses=item["max_uses"],
                used_count=0,
                is_active=True,
            )
        )
    db.commit()


DEMO_CLINICS = [
    {
        "clinic_name": "Sharma Family Clinic",
        "plan_slug": "professional",
        "billing_interval": "monthly",
    },
    {
        "clinic_name": "CarePlus Dental Clinic",
        "plan_slug": "starter",
        "billing_interval": "yearly",
    },
    {
        "clinic_name": "Wellness Physiotherapy Centre",
        "plan_slug": "enterprise",
        "billing_interval": "monthly",
    },
]


def _create_demo_subscription(
    db: Session,
    customer: Customer,
    *,
    plan_slug: str = "professional",
    billing_interval: str = "monthly",
    clinic_name: str | None = None,
) -> None:
    plan = db.query(Plan).filter(Plan.slug == plan_slug).first()
    if not plan:
        return

    plan_price = (
        db.query(PlanPrice)
        .filter(PlanPrice.plan_id == plan.id, PlanPrice.billing_interval == billing_interval)
        .first()
    )
    if not plan_price:
        return

    gst = calculate_gst(plan_price.amount, customer.state, get_company_state())
    now = datetime.now(timezone.utc)
    suffix = f"{int(now.timestamp())}_{plan_slug}_{billing_interval}"

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
        gateway_order_id=f"mock_order_demo_{suffix}",
        clinic_name=clinic_name or customer.clinic_name,
    )
    db.add(order)
    db.flush()

    subscription = Subscription(
        customer_id=customer.id,
        plan_id=plan.id,
        plan_price_id=plan_price.id,
        order_id=order.id,
        clinic_name=clinic_name or customer.clinic_name,
        status="active",
        billing_interval=billing_interval,
        current_period_start=now,
        current_period_end=now + timedelta(days=30 if billing_interval == "monthly" else 365),
        gateway_subscription_id=f"mock_sub_demo_{suffix}",
    )
    db.add(subscription)
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
        payment_method="mock",
        gateway_payment_id=f"mock_pay_demo_{suffix}",
        paid_at=now,
    )
    db.add(payment)
    db.commit()


def _seed_demo_customer(db: Session):
    existing = db.query(Customer).filter(Customer.email == DEMO_CUSTOMER["email"]).first()
    if existing:
        active_subs = (
            db.query(Subscription)
            .filter(Subscription.customer_id == existing.id, Subscription.status == "active")
            .all()
        )
        paid_payment = (
            db.query(Payment)
            .filter(Payment.customer_id == existing.id, Payment.status == "paid")
            .first()
        )
        if not active_subs or not paid_payment:
            _create_demo_subscription(db, existing, clinic_name=DEMO_CUSTOMER["clinic_name"])
            active_subs = (
                db.query(Subscription)
                .filter(Subscription.customer_id == existing.id, Subscription.status == "active")
                .all()
            )

        for sub in active_subs:
            if not sub.clinic_name:
                sub.clinic_name = existing.clinic_name or DEMO_CUSTOMER["clinic_name"]
        db.commit()

        clinic_names = {sub.clinic_name for sub in active_subs if sub.clinic_name}
        for clinic in DEMO_CLINICS:
            if clinic["clinic_name"] not in clinic_names:
                _create_demo_subscription(
                    db,
                    existing,
                    plan_slug=clinic["plan_slug"],
                    billing_interval=clinic["billing_interval"],
                    clinic_name=clinic["clinic_name"],
                )
        return

    customer = Customer(
        email=DEMO_CUSTOMER["email"],
        password_hash=hash_password(DEMO_CUSTOMER["password"]),
        name=DEMO_CUSTOMER["name"],
        phone=DEMO_CUSTOMER["phone"],
        clinic_name=DEMO_CUSTOMER["clinic_name"],
        gstin=DEMO_CUSTOMER["gstin"],
        billing_address=DEMO_CUSTOMER["billing_address"],
        state=DEMO_CUSTOMER["state"],
        city=DEMO_CUSTOMER["city"],
        pincode=DEMO_CUSTOMER["pincode"],
        email_verified=True,
    )
    db.add(customer)
    db.flush()
    for clinic in DEMO_CLINICS:
        _create_demo_subscription(
            db,
            customer,
            plan_slug=clinic["plan_slug"],
            billing_interval=clinic["billing_interval"],
            clinic_name=clinic["clinic_name"],
        )
