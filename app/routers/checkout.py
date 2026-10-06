import json
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.customer_auth import get_current_customer
from app.models.customer import Customer
from app.models.order import Order
from app.models.plan import Plan, PlanPrice
from app.schemas.commerce import (
    CheckoutAddonOut,
    CheckoutAuthenticatedRequest,
    CheckoutConfirmRequest,
    CheckoutConfirmResponse,
    CheckoutCreateRequest,
    CheckoutCreateResponse,
    CheckoutPreviewRequest,
    CheckoutPreviewResponse,
)
from app.services.checkout_addons import list_checkout_addons, resolve_checkout_addons
from app.services.commerce_utils import generate_order_number, get_company_state
from app.services.coupon_service import CouponError, build_pricing, get_coupon
from app.services.customer_auth import hash_password
from app.services.order_fulfillment import fulfill_paid_order
from app.services.payment_gateway import (
    create_gateway_order,
    get_payment_mode,
    get_razorpay_key_id,
    verify_razorpay_payment,
)

router = APIRouter(prefix="/checkout", tags=["Checkout"])


def _get_plan_price(db: Session, plan_slug: str, billing_interval: str) -> tuple[Plan, PlanPrice]:
    plan = db.query(Plan).filter(Plan.slug == plan_slug, Plan.is_active.is_(True)).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    plan_price = (
        db.query(PlanPrice)
        .filter(
            PlanPrice.plan_id == plan.id,
            PlanPrice.billing_interval == billing_interval,
            PlanPrice.is_active.is_(True),
        )
        .first()
    )
    if not plan_price:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan price not found")

    return plan, plan_price


def _resolve_checkout_pricing(
    db: Session,
    *,
    plan_price: PlanPrice,
    customer_state: str,
    billing_interval: str,
    coupon_code: str | None,
    addon_slugs: list[str] | None,
):
    try:
        selected_addons, addons_total = resolve_checkout_addons(addon_slugs)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    coupon = get_coupon(db, coupon_code)
    base_amount = Decimal(str(plan_price.amount)) + addons_total
    try:
        pricing = build_pricing(
            plan_amount=base_amount,
            customer_state=customer_state,
            company_state=get_company_state(),
            coupon=coupon,
            billing_interval=billing_interval,
        )
    except CouponError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    pricing["selected_addons"] = selected_addons
    pricing["addons_total"] = addons_total
    pricing["plan_amount"] = Decimal(str(plan_price.amount)).quantize(Decimal("0.01"))
    pricing["addons_json"] = json.dumps(selected_addons, default=str) if selected_addons else None
    return pricing


@router.get("/addons", response_model=list[CheckoutAddonOut])
def get_checkout_addons():
    return [CheckoutAddonOut(**item) for item in list_checkout_addons()]


@router.post("/preview", response_model=CheckoutPreviewResponse)
def preview_checkout(payload: CheckoutPreviewRequest, db: Session = Depends(get_db)):
    plan, plan_price = _get_plan_price(db, payload.plan_slug, payload.billing_interval)
    pricing = _resolve_checkout_pricing(
        db,
        plan_price=plan_price,
        customer_state=payload.customer_state,
        billing_interval=plan_price.billing_interval,
        coupon_code=payload.coupon_code,
        addon_slugs=payload.addon_slugs,
    )

    return CheckoutPreviewResponse(
        plan_slug=plan.slug,
        plan_name=plan.name,
        billing_interval=plan_price.billing_interval,
        plan_amount=pricing["plan_amount"],
        addons_total=pricing["addons_total"],
        selected_addons=pricing["selected_addons"],
        subtotal=pricing["subtotal"],
        cgst=pricing["cgst"],
        sgst=pricing["sgst"],
        igst=pricing["igst"],
        gst_total=pricing["gst_total"],
        total=pricing["total"],
        is_intra_state=pricing["is_intra_state"],
        discount_amount=pricing["discount_amount"],
        coupon_code=pricing["coupon_code"],
        trial_days=pricing["trial_days"],
    )


@router.post("/create", response_model=CheckoutCreateResponse)
def create_checkout(payload: CheckoutCreateRequest, db: Session = Depends(get_db)):
    plan, plan_price = _get_plan_price(db, payload.plan_slug, payload.billing_interval)
    pricing = _resolve_checkout_pricing(
        db,
        plan_price=plan_price,
        customer_state=payload.state,
        billing_interval=plan_price.billing_interval,
        coupon_code=payload.coupon_code,
        addon_slugs=payload.addon_slugs,
    )

    customer = db.query(Customer).filter(Customer.email == payload.email.lower()).first()
    if customer:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please log in instead.",
        )

    customer = Customer(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
        phone=payload.phone,
        clinic_name=payload.clinic_name,
        gstin=payload.gstin,
        billing_address=payload.billing_address,
        state=payload.state,
        city=payload.city,
        pincode=payload.pincode,
        email_verified=False,
    )
    db.add(customer)
    db.flush()

    order_number = generate_order_number(db)
    gateway = create_gateway_order(
        order_number=order_number,
        total=pricing["total"],
        customer_email=customer.email,
        customer_phone=customer.phone or "",
    )

    order = Order(
        order_number=order_number,
        customer_id=customer.id,
        plan_price_id=plan_price.id,
        status="pending",
        subtotal=pricing["subtotal"],
        cgst=pricing["cgst"],
        sgst=pricing["sgst"],
        igst=pricing["igst"],
        gst_total=pricing["gst_total"],
        total=pricing["total"],
        coupon_code=pricing["coupon_code"],
        discount_amount=pricing["discount_amount"],
        trial_days=pricing["trial_days"],
        gateway_order_id=gateway["gateway_order_id"],
        clinic_name=payload.clinic_name,
        addons_json=pricing["addons_json"],
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return CheckoutCreateResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        total=order.total,
        payment_mode=get_payment_mode(),
        razorpay_key_id=gateway.get("razorpay_key_id") or get_razorpay_key_id(),
        razorpay_order_id=gateway["gateway_order_id"],
        amount_paise=gateway["amount_paise"],
        message="Order created. Complete payment to activate your subscription.",
        discount_amount=pricing["discount_amount"],
        coupon_code=pricing["coupon_code"],
    )


@router.post("/create-authenticated", response_model=CheckoutCreateResponse)
def create_authenticated_checkout(
    payload: CheckoutAuthenticatedRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    clinic_name = (payload.clinic_name or customer.clinic_name or "").strip()
    if not clinic_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clinic name is required to add a clinic subscription.",
        )

    plan, plan_price = _get_plan_price(db, payload.plan_slug, payload.billing_interval)
    pricing = _resolve_checkout_pricing(
        db,
        plan_price=plan_price,
        customer_state=customer.state,
        billing_interval=plan_price.billing_interval,
        coupon_code=payload.coupon_code,
        addon_slugs=payload.addon_slugs,
    )

    order_number = generate_order_number(db)
    gateway = create_gateway_order(
        order_number=order_number,
        total=pricing["total"],
        customer_email=customer.email,
        customer_phone=customer.phone or "",
    )

    order = Order(
        order_number=order_number,
        customer_id=customer.id,
        plan_price_id=plan_price.id,
        status="pending",
        subtotal=pricing["subtotal"],
        cgst=pricing["cgst"],
        sgst=pricing["sgst"],
        igst=pricing["igst"],
        gst_total=pricing["gst_total"],
        total=pricing["total"],
        coupon_code=pricing["coupon_code"],
        discount_amount=pricing["discount_amount"],
        trial_days=pricing["trial_days"],
        gateway_order_id=gateway["gateway_order_id"],
        order_type="checkout",
        clinic_name=clinic_name,
        addons_json=pricing["addons_json"],
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return CheckoutCreateResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        total=order.total,
        payment_mode=get_payment_mode(),
        razorpay_key_id=gateway.get("razorpay_key_id") or get_razorpay_key_id(),
        razorpay_order_id=gateway["gateway_order_id"],
        amount_paise=gateway["amount_paise"],
        message="Order created. Complete payment to activate your clinic subscription.",
        discount_amount=pricing["discount_amount"],
        coupon_code=pricing["coupon_code"],
    )


@router.post("/confirm/{order_id}", response_model=CheckoutConfirmResponse)
def confirm_checkout(
    order_id: int,
    payload: CheckoutConfirmRequest = CheckoutConfirmRequest(),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status == "paid":
        result = fulfill_paid_order(db, order=order)
        return CheckoutConfirmResponse(**result)

    if order.total > 0 and get_payment_mode() == "razorpay":
        if not payload.razorpay_payment_id or not payload.razorpay_signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Razorpay payment details are required")

        if not verify_razorpay_payment(
            gateway_order_id=order.gateway_order_id,
            gateway_payment_id=payload.razorpay_payment_id,
            signature=payload.razorpay_signature,
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment verification failed")

        gateway_payment_id = payload.razorpay_payment_id
    else:
        gateway_payment_id = f"mock_pay_{uuid.uuid4().hex[:12]}"

    try:
        result = fulfill_paid_order(db, order=order, gateway_payment_id=gateway_payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CheckoutConfirmResponse(**result)
