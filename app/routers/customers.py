from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps.customer_auth import get_current_customer
from app.models.customer import Customer
from app.models.credit_note import CreditNote
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.schemas.commerce import (
    BillingSummaryOut,
    ChangePasswordRequest,
    CustomerLoginRequest,
    CustomerLoginResponse,
    CustomerProfile,
    CustomerProfileUpdate,
    CustomerCreditNoteOut,
    ForgotPasswordRequest,
    InvoiceOut,
    MessageResponse,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
    PlanChangeConfirmRequest,
    PlanChangePreviewResponse,
    PlanChangeResponse,
    ReactivateResponse,
    ResetPasswordRequest,
    ResubscribePreviewResponse,
    ResubscribeRequest,
    ResubscribeResponse,
    RetryPaymentPreviewResponse,
    RetryPaymentResponse,
    SubscriptionCancelResponse,
    SubscriptionChangeRequest,
    SubscriptionOut,
)
from app.services.billing_summary_service import build_billing_summary
from app.services.email_service import send_payment_receipt_email
from app.services.customer_auth import create_access_token, verify_password
from app.services.password_reset_service import (
    change_customer_password,
    request_password_reset,
    reset_password_with_token,
)
from app.services.plan_change_service import confirm_plan_change, initiate_plan_change, preview_plan_change
from app.services.resubscribe_service import confirm_resubscribe, initiate_resubscribe, preview_resubscribe
from app.services.retry_payment_service import (
    confirm_retry_payment,
    get_retryable_subscription,
    initiate_retry_payment,
    preview_retry_payment,
)
from app.services.subscription_service import (
    cancel_subscription,
    get_active_subscription,
    get_cancelled_subscription,
    get_customer_subscription,
    list_customer_subscriptions,
    reactivate_subscription,
)

router = APIRouter(prefix="/customers", tags=["Customers"])


def _subscription_response(subscription, plan_price: PlanPrice | None) -> SubscriptionOut:
    return SubscriptionOut(
        id=subscription.id,
        status=subscription.status,
        billing_interval=subscription.billing_interval,
        plan_name=subscription.plan.name,
        plan_slug=subscription.plan.slug,
        clinic_name=subscription.clinic_name,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        amount=plan_price.amount if plan_price else 0,
        cancelled_at=subscription.cancelled_at,
        cancel_at_period_end=subscription.status == "cancelled",
    )


@router.post("/login", response_model=CustomerLoginResponse)
def login(payload: CustomerLoginRequest, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.email == payload.email.lower(), Customer.is_active.is_(True)).first()
    if not customer or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return CustomerLoginResponse(
        access_token=create_access_token(customer.id, customer.email),
        email=customer.email,
        name=customer.name,
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    request_password_reset(db, email=payload.email)
    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent.",
    )


@router.post("/reset-password", response_model=CustomerLoginResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        customer = reset_password_with_token(db, token=payload.token, new_password=payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CustomerLoginResponse(
        access_token=create_access_token(customer.id, customer.email),
        email=customer.email,
        name=customer.name,
    )


@router.post("/me/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    try:
        change_customer_password(
            db,
            customer=customer,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return MessageResponse(message="Password updated successfully.")


@router.get("/me", response_model=CustomerProfile)
def get_profile(customer: Customer = Depends(get_current_customer)):
    return CustomerProfile.model_validate(customer)


@router.put("/me", response_model=CustomerProfile)
def update_profile(
    payload: CustomerProfileUpdate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return CustomerProfile.model_validate(customer)

    for field, value in updates.items():
        if field == "gstin" and value:
            value = value.upper()
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return CustomerProfile.model_validate(customer)


@router.get("/me/notification-preferences", response_model=NotificationPreferencesOut)
def get_notification_preferences(customer: Customer = Depends(get_current_customer)):
    return NotificationPreferencesOut(
        notify_email_billing=customer.notify_email_billing,
        notify_email_marketing=customer.notify_email_marketing,
        notify_sms_billing=customer.notify_sms_billing,
    )


@router.put("/me/notification-preferences", response_model=NotificationPreferencesOut)
def update_notification_preferences(
    payload: NotificationPreferencesUpdate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return NotificationPreferencesOut(
        notify_email_billing=customer.notify_email_billing,
        notify_email_marketing=customer.notify_email_marketing,
        notify_sms_billing=customer.notify_sms_billing,
    )


@router.get("/me/billing-summary", response_model=BillingSummaryOut)
def get_billing_summary(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    return BillingSummaryOut(**build_billing_summary(db, customer=customer))


@router.get("/me/subscriptions", response_model=list[SubscriptionOut])
def get_my_subscriptions(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    subscriptions = list_customer_subscriptions(db, customer.id)
    return [
        _subscription_response(subscription, subscription.plan_price)
        for subscription in subscriptions
    ]


@router.get("/me/subscription", response_model=SubscriptionOut)
def get_my_subscription(
    subscription_id: int | None = None,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    subscription = get_customer_subscription(db, customer.id, subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")

    plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
    return _subscription_response(subscription, plan_price)


@router.post("/me/subscription/cancel", response_model=SubscriptionCancelResponse)
def cancel_my_subscription(
    subscription_id: int | None = None,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    subscription = get_customer_subscription(db, customer.id, subscription_id)
    if not subscription or subscription.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No cancellable subscription found")

    try:
        updated = cancel_subscription(db, subscription, customer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SubscriptionCancelResponse(
        subscription_id=updated.id,
        status=updated.status,
        current_period_end=updated.current_period_end,
        message="Subscription cancelled. Access continues until the end of your billing period.",
    )


@router.get("/me/subscription/retry-payment/preview", response_model=RetryPaymentPreviewResponse)
def preview_retry_payment_plan(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    subscription = get_retryable_subscription(db, customer.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No past-due subscription found that requires payment.",
        )
    try:
        preview = preview_retry_payment(db, customer=customer, subscription=subscription)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RetryPaymentPreviewResponse(**preview)


@router.post("/me/subscription/retry-payment", response_model=RetryPaymentResponse)
def retry_subscription_payment(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    subscription = get_retryable_subscription(db, customer.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No past-due subscription found that requires payment.",
        )
    try:
        result = initiate_retry_payment(db, customer=customer, subscription=subscription)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RetryPaymentResponse(**result)


@router.post("/me/subscription/retry-payment/confirm/{order_id}", response_model=SubscriptionOut)
def confirm_retry_subscription_payment(
    order_id: int,
    payload: PlanChangeConfirmRequest = PlanChangeConfirmRequest(),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id, Order.order_type == "retry_payment")
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retry payment order not found")

    try:
        confirm_retry_payment(
            db,
            order=order,
            customer=customer,
            gateway_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    subscription = get_active_subscription(db, customer.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Subscription not restored")

    plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
    return _subscription_response(subscription, plan_price)


@router.post("/me/subscription/reactivate", response_model=ReactivateResponse)
def reactivate_my_subscription(
    subscription_id: int | None = None,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if subscription_id is not None:
        subscription = get_customer_subscription(db, customer.id, subscription_id)
        if not subscription or subscription.status != "cancelled":
            subscription = None
    else:
        subscription = get_cancelled_subscription(db, customer.id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cancelled subscription found that can be reactivated.",
        )

    try:
        updated = reactivate_subscription(db, subscription, customer)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    plan_price = db.query(PlanPrice).filter(PlanPrice.id == updated.plan_price_id).first()
    return ReactivateResponse(
        subscription=_subscription_response(updated, plan_price),
        message="Subscription reactivated. Your plan will renew as scheduled.",
    )


@router.post("/me/subscription/resubscribe/preview", response_model=ResubscribePreviewResponse)
def preview_resubscribe_plan(
    payload: ResubscribeRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if get_active_subscription(db, customer.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active subscription.",
        )

    try:
        preview = preview_resubscribe(
            db,
            customer=customer,
            plan_slug=payload.plan_slug,
            billing_interval=payload.billing_interval,
            coupon_code=payload.coupon_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ResubscribePreviewResponse(**preview)


@router.post("/me/subscription/resubscribe", response_model=ResubscribeResponse)
def resubscribe_plan(
    payload: ResubscribeRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if get_active_subscription(db, customer.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active subscription.",
        )

    try:
        result = initiate_resubscribe(
            db,
            customer=customer,
            plan_slug=payload.plan_slug,
            billing_interval=payload.billing_interval,
            coupon_code=payload.coupon_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result.get("applied_immediately"):
        subscription = get_active_subscription(db, customer.id)
        plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first() if subscription else None
        return ResubscribeResponse(
            applied_immediately=True,
            message=result["message"],
            subscription=_subscription_response(subscription, plan_price) if subscription else None,
            total=result.get("total"),
        )

    return ResubscribeResponse(
        applied_immediately=False,
        message=result["message"],
        order_id=result["order_id"],
        order_number=result["order_number"],
        total=result["total"],
        payment_mode=result["payment_mode"],
        razorpay_key_id=result["razorpay_key_id"],
        razorpay_order_id=result["razorpay_order_id"],
        amount_paise=result["amount_paise"],
    )


@router.post("/me/subscription/resubscribe/confirm/{order_id}", response_model=SubscriptionOut)
def confirm_resubscribe_plan(
    order_id: int,
    payload: PlanChangeConfirmRequest = PlanChangeConfirmRequest(),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id, Order.order_type == "resubscribe")
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resubscribe order not found")

    try:
        confirm_resubscribe(
            db,
            order=order,
            customer=customer,
            gateway_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    subscription = get_active_subscription(db, customer.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Subscription not activated")

    plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
    return _subscription_response(subscription, plan_price)


@router.post("/me/subscription/change-plan/preview", response_model=PlanChangePreviewResponse)
def preview_my_plan_change(
    payload: SubscriptionChangeRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    subscription = get_customer_subscription(db, customer.id, payload.subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")

    try:
        preview = preview_plan_change(
            db,
            subscription=subscription,
            customer=customer,
            plan_slug=payload.plan_slug,
            billing_interval=payload.billing_interval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return PlanChangePreviewResponse(**preview)


@router.post("/me/subscription/change-plan", response_model=PlanChangeResponse)
def change_my_plan(
    payload: SubscriptionChangeRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    subscription = get_customer_subscription(db, customer.id, payload.subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")

    try:
        result = initiate_plan_change(
            db,
            subscription=subscription,
            customer=customer,
            plan_slug=payload.plan_slug,
            billing_interval=payload.billing_interval,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result["applied_immediately"]:
        plan_price = db.query(PlanPrice).filter(PlanPrice.id == result["subscription"].plan_price_id).first()
        return PlanChangeResponse(
            applied_immediately=True,
            message=result["message"],
            subscription=_subscription_response(result["subscription"], plan_price),
        )

    return PlanChangeResponse(
        applied_immediately=False,
        message=result["message"],
        order_id=result["order_id"],
        order_number=result["order_number"],
        total=result["total"],
        payment_mode=result["payment_mode"],
        razorpay_key_id=result["razorpay_key_id"],
        razorpay_order_id=result["razorpay_order_id"],
        amount_paise=result["amount_paise"],
    )


@router.post("/me/subscription/change-plan/confirm/{order_id}", response_model=SubscriptionOut)
def confirm_my_plan_change(
    order_id: int,
    payload: PlanChangeConfirmRequest = PlanChangeConfirmRequest(),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == customer.id, Order.order_type == "plan_change")
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan change order not found")

    try:
        subscription = confirm_plan_change(
            db,
            order=order,
            customer=customer,
            gateway_payment_id=payload.razorpay_payment_id,
            razorpay_signature=payload.razorpay_signature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    plan_price = db.query(PlanPrice).filter(PlanPrice.id == subscription.plan_price_id).first()
    return _subscription_response(subscription, plan_price)


@router.get("/me/invoices", response_model=list[InvoiceOut])
def get_my_invoices(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    return [InvoiceOut.model_validate(payment) for payment in payments]


@router.get("/me/invoices/{payment_id}/pdf")
def download_invoice_pdf(
    payment_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.customer_id == customer.id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if not payment.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice PDF is not available")

    uploads_root = Path(__file__).resolve().parents[2] / "uploads"
    file_path = uploads_root / payment.pdf_path

    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice PDF file missing")

    filename = f"{payment.invoice_number.replace('/', '-')}.pdf"
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


@router.post("/me/invoices/{payment_id}/resend", response_model=MessageResponse)
def resend_invoice_email(
    payment_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.customer_id == customer.id, Payment.status == "paid")
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    plan_name = "ClinicPro"
    if payment.subscription_id:
        subscription = (
            db.query(Subscription)
            .options(joinedload(Subscription.plan))
            .filter(Subscription.id == payment.subscription_id)
            .first()
        )
        if subscription and subscription.plan:
            plan_name = subscription.plan.name
    elif payment.order_id:
        order = db.query(Order).filter(Order.id == payment.order_id).first()
        if order:
            plan_price = db.query(PlanPrice).filter(PlanPrice.id == order.plan_price_id).first()
            if plan_price:
                plan = db.query(Plan).filter(Plan.id == plan_price.plan_id).first()
                if plan:
                    plan_name = plan.name

    uploads_root = Path(__file__).resolve().parents[2] / "uploads"
    send_payment_receipt_email(db, customer, payment, plan_name, uploads_root, force=True)
    db.commit()
    return MessageResponse(message=f"Invoice {payment.invoice_number} resent to {customer.email}.")


@router.get("/me/credit-notes", response_model=list[CustomerCreditNoteOut])
def get_my_credit_notes(customer: Customer = Depends(get_current_customer), db: Session = Depends(get_db)):
    notes = (
        db.query(CreditNote)
        .filter(CreditNote.customer_id == customer.id)
        .order_by(CreditNote.created_at.desc())
        .all()
    )
    results = []
    for note in notes:
        payment = db.query(Payment).filter(Payment.id == note.payment_id).first()
        results.append(
            CustomerCreditNoteOut(
                id=note.id,
                credit_note_number=note.credit_note_number,
                invoice_number=payment.invoice_number if payment else "",
                amount=note.amount,
                reason=note.reason,
                status=note.status,
                pdf_path=note.pdf_path,
                created_at=note.created_at,
            )
        )
    return results


@router.get("/me/credit-notes/{credit_note_id}/pdf")
def download_credit_note_pdf(
    credit_note_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    note = (
        db.query(CreditNote)
        .filter(CreditNote.id == credit_note_id, CreditNote.customer_id == customer.id)
        .first()
    )
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit note not found")

    if not note.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit note PDF is not available")

    uploads_root = Path(__file__).resolve().parents[2] / "uploads"
    file_path = uploads_root / note.pdf_path

    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit note PDF file missing")

    filename = f"{note.credit_note_number.replace('/', '-')}.pdf"
    return FileResponse(file_path, media_type="application/pdf", filename=filename)
