from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps.admin_auth import require_admin
from app.models.contact_submission import ContactSubmission
from app.models.coupon import Coupon
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.email_log import EmailLog
from app.models.order import Order
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.models.subscription import Subscription
from app.schemas.commerce import (
    AdminCustomerDetailOut,
    AdminCommerceAnalytics,
    AdminCommerceStats,
    AdminCouponOut,
    AdminCreditNoteOut,
    AdminCustomerOut,
    AdminEmailLogOut,
    AdminOrderOut,
    AdminPaymentOut,
    AdminSubscriptionActionResponse,
    AdminSubscriptionExtendRequest,
    AdminSubscriptionOut,
    AdminSubscriptionRenewResponse,
    CouponCreateRequest,
    CouponUpdateRequest,
    CreditNoteOut,
    MessageResponse,
    RefundRequest,
)
from app.schemas.contact import ContactSubmissionOut
from app.services.admin_customer_service import build_admin_customer_detail, customer_has_purchase
from app.services.admin_subscription_service import (
    admin_cancel_subscription,
    admin_reactivate_subscription,
    admin_renew_subscription,
    extend_subscription,
)
from app.services.commerce_analytics_service import build_commerce_analytics
from app.services.credit_note_service import issue_refund
from app.services.email_service import send_payment_receipt_email
from app.services.gst_export_service import build_gst_export_csv

router = APIRouter(prefix="/admin/commerce", tags=["Admin Commerce"], dependencies=[Depends(require_admin)])


def _monthly_amount(amount: Decimal, billing_interval: str) -> Decimal:
    if billing_interval == "yearly":
        return (amount / Decimal("12")).quantize(Decimal("0.01"))
    return Decimal(str(amount)).quantize(Decimal("0.01"))


@router.get("/stats", response_model=AdminCommerceStats)
def commerce_stats(db: Session = Depends(get_db)):
    active_subs = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan_price))
        .filter(Subscription.status == "active")
        .all()
    )
    mrr = sum(_monthly_amount(sub.plan_price.amount, sub.billing_interval) for sub in active_subs if sub.plan_price)

    total_revenue = db.query(func.coalesce(func.sum(Payment.total), 0)).filter(Payment.status == "paid").scalar()

    return AdminCommerceStats(
        total_customers=db.query(Customer).count(),
        active_subscriptions=len(active_subs),
        cancelled_subscriptions=db.query(Subscription).filter(Subscription.status == "cancelled").count(),
        pending_orders=db.query(Order).filter(Order.status == "pending").count(),
        total_revenue=Decimal(str(total_revenue or 0)),
        mrr=Decimal(str(mrr)),
        new_contact_submissions=db.query(ContactSubmission).filter(ContactSubmission.status == "new").count(),
    )


@router.get("/analytics", response_model=AdminCommerceAnalytics)
def commerce_analytics(db: Session = Depends(get_db)):
    return AdminCommerceAnalytics(**build_commerce_analytics(db))


@router.get("/customers", response_model=list[AdminCustomerOut])
def list_customers(
    purchased_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    custom.= db.query(Customer).order_by(Customer.created_at.desc()).limit(200).all()
    results = []
    for customer in customers:
        if purchased_only and not customer_has_purchase(db, customer.id):
            continue

        sub = (
            db.query(Subscription)
            .options(joinedload(Subscription.plan))
            .filter(Subscription.customer_id == customer.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
        results.append(
            AdminCustomerOut(
                id=customer.id,
                name=customer.name,
                email=customer.email,
                clinic_name=customer.clinic_name,
                phone=customer.phone,
                state=customer.state,
                created_at=customer.created_at,
                active_plan=sub.plan.name if sub and sub.plan else None,
                subscription_status=sub.status if sub else None,
            )
        )
    return results


@router.get("/customers/{customer_id}", response_model=AdminCustomerDetailOut)
def get_customer_detail(customer_id: int, db: Session = Depends(get_db)):
    try:
        detail = build_admin_customer_detail(db, customer_id=customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AdminCustomerDetailOut(**detail)


@router.get("/customers/{customer_id}/invoices/{payment_id}/pdf")
def download_customer_invoice_pdf(customer_id: int, payment_id: int, db: Session = Depends(get_db)):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.customer_id == customer_id)
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


@router.post("/customers/{customer_id}/invoices/{payment_id}/resend", response_model=MessageResponse)
def resend_customer_invoice_email(customer_id: int, payment_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

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


@router.get("/customers/{customer_id}/credit-notes/{credit_note_id}/pdf")
def download_customer_credit_note_pdf(customer_id: int, credit_note_id: int, db: Session = Depends(get_db)):
    note = (
        db.query(CreditNote)
        .filter(CreditNote.id == credit_note_id, CreditNote.customer_id == customer_id)
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


@router.get("/orders", response_model=list[AdminOrderOut])
def list_orders(db: Session = Depends(get_db)):
    ord.= db.query(Order).order_by(Order.created_at.desc()).limit(100).all()
    results = []
    for order in orders:
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        results.append(
            AdminOrderOut(
                id=order.id,
                order_number=order.order_number,
                customer_email=customer.email if customer else "",
                customer_name=customer.name if customer else "",
                order_type=order.order_type or "checkout",
                status=order.status,
                total=order.total,
                coupon_code=order.coupon_code,
                created_at=order.created_at,
            )
        )
    return results


@router.get("/payments", response_model=list[AdminPaymentOut])
def list_payments(db: Session = Depends(get_db)):
    payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(100).all()
    results = []
    for payment in payments:
        customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
        results.append(
            AdminPaymentOut(
                id=payment.id,
                invoice_number=payment.invoice_number,
                customer_email=customer.email if customer else "",
                total=payment.total,
                status=payment.status,
                payment_method=payment.payment_method,
                paid_at=payment.paid_at,
            )
        )
    return results


@router.get("/subscriptions", response_model=list[AdminSubscriptionOut])
def list_subscriptions(db: Session = Depends(get_db)):
    subs = (
        db.query(Subscription)
        .options(joinedload(Subscription.plan), joinedload(Subscription.plan_price), joinedload(Subscription.customer))
        .order_by(Subscription.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        AdminSubscriptionOut(
            id=sub.id,
            customer_email=sub.customer.email if sub.customer else "",
            customer_name=sub.customer.name if sub.customer else "",
            plan_name=sub.plan.name if sub.plan else "",
            billing_interval=sub.billing_interval,
            status=sub.status,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            amount=sub.plan_price.amount if sub.plan_price else Decimal("0"),
            gateway_subscription_id=sub.gateway_subscription_id,
        )
        for sub in subs
    ]


@router.post("/subscriptions/{subscription_id}/extend", response_model=AdminSubscriptionActionResponse)
def extend_subscription_period(
    subscription_id: int,
    payload: AdminSubscriptionExtendRequest,
    db: Session = Depends(get_db),
):
    try:
        updated = extend_subscription(db, subscription_id=subscription_id, days=payload.days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AdminSubscriptionActionResponse(
        subscription_id=updated.id,
        status=updated.status,
        current_period_end=updated.current_period_end,
        message=f"Subscription extended by {payload.days} days.",
    )


@router.post("/subscriptions/{subscription_id}/cancel", response_model=AdminSubscriptionActionResponse)
def cancel_subscription_admin(subscription_id: int, db: Session = Depends(get_db)):
    try:
        updated = admin_cancel_subscription(db, subscription_id=subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AdminSubscriptionActionResponse(
        subscription_id=updated.id,
        status=updated.status,
        current_period_end=updated.current_period_end,
        message="Subscription cancelled at period end.",
    )


@router.post("/subscriptions/{subscription_id}/reactivate", response_model=AdminSubscriptionActionResponse)
def reactivate_subscription_admin(subscription_id: int, db: Session = Depends(get_db)):
    try:
        updated = admin_reactivate_subscription(db, subscription_id=subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AdminSubscriptionActionResponse(
        subscription_id=updated.id,
        status=updated.status,
        current_period_end=updated.current_period_end,
        message="Subscription reactivated.",
    )


@router.post("/subscriptions/{subscription_id}/renew", response_model=AdminSubscriptionRenewResponse)
def renew_subscription_admin(subscription_id: int, db: Session = Depends(get_db)):
    try:
        result = admin_renew_subscription(db, subscription_id=subscription_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AdminSubscriptionRenewResponse(
        **result,
        message="Renewal invoice generated and subscription period updated.",
    )


@router.get("/email-logs", response_model=list[AdminEmailLogOut])
def list_email_logs(db: Session = Depends(get_db)):
    logs = db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(100).all()
    return [AdminEmailLogOut.model_validate(log) for log in logs]


@router.get("/contact-submissions", response_model=list[ContactSubmissionOut])
def list_contact_submissions(db: Session = Depends(get_db)):
    submissions = db.query(ContactSubmission).order_by(ContactSubmission.created_at.desc()).limit(100).all()
    return [
        ContactSubmissionOut(
            id=item.id,
            full_name=item.full_name,
            email=item.email,
            phone=item.phone,
            clinic_name=item.clinic_name,
            inquiry_type=item.inquiry_type,
            message=item.message,
            status=item.status,
            created_at=item.created_at.isoformat(),
        )
        for item in submissions
    ]


@router.patch("/contact-submissions/{submission_id}/read")
def mark_contact_read(submission_id: int, db: Session = Depends(get_db)):
    submission = db.query(ContactSubmission).filter(ContactSubmission.id == submission_id).first()
    if submission:
        submission.status = "read"
        db.commit()
    return {"status": "ok"}


@router.get("/coupons", response_model=list[AdminCouponOut])
def list_coupons(db: Session = Depends(get_db)):
    coupons = db.query(Coupon).order_by(Coupon.code.asc()).all()
    return [AdminCouponOut.model_validate(coupon) for coupon in coupons]


@router.post("/coupons", response_model=AdminCouponOut, status_code=status.HTTP_201_CREATED)
def create_coupon(payload: CouponCreateRequest, db: Session = Depends(get_db)):
    code = payload.code.strip().upper()
    existing = db.query(Coupon).filter(Coupon.code == code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coupon code already exists")

    if payload.discount_type == "percent" and payload.discount_value > Decimal("100"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Percent discount cannot exceed 100")

    coupon = Coupon(
        code=code,
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        billing_interval=payload.billing_interval,
        trial_days=payload.trial_days,
        max_uses=payload.max_uses,
        used_count=0,
        is_active=payload.is_active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return AdminCouponOut.model_validate(coupon)


@router.put("/coupons/{coupon_id}", response_model=AdminCouponOut)
def update_coupon(coupon_id: int, payload: CouponUpdateRequest, db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    updates = payload.model_dump(exclude_unset=True)
    discount_type = updates.get("discount_type", coupon.discount_type)
    discount_value = updates.get("discount_value", coupon.discount_value)
    if discount_type == "percent" and Decimal(str(discount_value)) > Decimal("100"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Percent discount cannot exceed 100")

    for field, value in updates.items():
        setattr(coupon, field, value)

    db.commit()
    db.refresh(coupon)
    return AdminCouponOut.model_validate(coupon)


@router.patch("/coupons/{coupon_id}/toggle", response_model=AdminCouponOut)
def toggle_coupon(coupon_id: int, db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    coupon.is_active = not coupon.is_active
    db.commit()
    db.refresh(coupon)
    return AdminCouponOut.model_validate(coupon)


@router.get("/credit-notes", response_model=list[AdminCreditNoteOut])
def list_credit_notes(db: Session = Depends(get_db)):
    notes = (
        db.query(CreditNote)
        .options(joinedload(CreditNote.customer), joinedload(CreditNote.payment))
        .order_by(CreditNote.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        AdminCreditNoteOut(
            id=note.id,
            credit_note_number=note.credit_note_number,
            customer_email=note.customer.email if note.customer else "",
            customer_name=note.customer.name if note.customer else "",
            invoice_number=note.payment.invoice_number if note.payment else "",
            amount=note.amount,
            reason=note.reason,
            status=note.status,
            created_at=note.created_at,
        )
        for note in notes
    ]


@router.post("/payments/{payment_id}/refund", response_model=CreditNoteOut)
def refund_payment(payment_id: int, payload: RefundRequest, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    try:
        credit_note = issue_refund(db, payment=payment, customer=customer, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CreditNoteOut.model_validate(credit_note)


@router.get("/export/gst.csv")
def export_gst_csv(db: Session = Depends(get_db)):
    csv_content = build_gst_export_csv(db)
    filename = f"clinicpro-gst-export-{__import__('datetime').datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
