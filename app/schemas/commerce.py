from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class PlanPriceOut(BaseModel):
    id: int
    billing_interval: str
    amount: Decimal
    currency: str

    class Config:
        from_attributes = True


class PlanOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    features: list[str]
    is_popular: bool
    prices: list[PlanPriceOut]

    class Config:
        from_attributes = True


class CheckoutPreviewRequest(BaseModel):
    plan_slug: str
    billing_interval: Literal["monthly", "yearly"] = "monthly"
    customer_state: str = "Maharashtra"
    coupon_code: Optional[str] = None
    addon_slugs: list[str] = Field(default_factory=list)


class CheckoutAddonOut(BaseModel):
    slug: str
    icon: str
    title: str
    description: str
    price_label: str
    amount: Decimal
    billing_label: str = ""


class CheckoutAddonLineOut(BaseModel):
    slug: str
    title: str
    amount: Decimal
    billing_label: str = ""


class CheckoutPreviewResponse(BaseModel):
    plan_slug: str
    plan_name: str
    billing_interval: str
    plan_amount: Decimal = Decimal("0.00")
    addons_total: Decimal = Decimal("0.00")
    selected_addons: list[CheckoutAddonLineOut] = Field(default_factory=list)
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    is_intra_state: bool
    currency: str = "INR"
    discount_amount: Decimal = Decimal("0.00")
    coupon_code: Optional[str] = None
    trial_days: Optional[int] = None


class CheckoutCreateRequest(BaseModel):
    plan_slug: str
    billing_interval: Literal["monthly", "yearly"] = "monthly"
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)
    clinic_name: str = Field(min_length=2, max_length=180)
    password: str = Field(min_length=6, max_length=128)
    gstin: Optional[str] = Field(default=None, max_length=15)
    billing_address: str = Field(min_length=5, max_length=500)
    state: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    pincode: str = Field(min_length=5, max_length=10)
    coupon_code: Optional[str] = Field(default=None, max_length=30)
    addon_slugs: list[str] = Field(default_factory=list)


class CheckoutAuthenticatedRequest(BaseModel):
    plan_slug: str
    billing_interval: Literal["monthly", "yearly"] = "monthly"
    clinic_name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    coupon_code: Optional[str] = Field(default=None, max_length=30)
    addon_slugs: list[str] = Field(default_factory=list)


class BillingSummaryOut(BaseModel):
    payment_method: str
    payment_method_label: str
    has_active_subscription: bool
    subscription_status: Optional[str] = None
    plan_name: Optional[str] = None
    billing_interval: Optional[str] = None
    next_renewal_date: Optional[datetime] = None
    next_renewal_amount: Optional[Decimal] = None
    last_invoice_number: Optional[str] = None
    last_payment_date: Optional[datetime] = None
    last_payment_amount: Optional[Decimal] = None
    total_spent: Decimal
    invoice_count: int


class NotificationPreferencesOut(BaseModel):
    notify_email_billing: bool
    notify_email_marketing: bool
    notify_sms_billing: bool


class NotificationPreferencesUpdate(BaseModel):
    notify_email_billing: Optional[bool] = None
    notify_email_marketing: Optional[bool] = None
    notify_sms_billing: Optional[bool] = None


class MessageResponse(BaseModel):
    message: str


class CheckoutCreateResponse(BaseModel):
    order_id: int
    order_number: str
    status: str
    total: Decimal
    payment_mode: str
    razorpay_key_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    amount_paise: Optional[int] = None
    message: str
    discount_amount: Decimal = Decimal("0.00")
    coupon_code: Optional[str] = None


class CheckoutConfirmRequest(BaseModel):
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None


class CheckoutConfirmResponse(BaseModel):
    order_id: int
    order_number: str
    invoice_number: str
    subscription_id: int
    subscription_status: str
    current_period_end: datetime
    total: Decimal
    access_token: str
    customer_email: str


class CustomerLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CustomerLoginResponse(BaseModel):
    access_token: str
    email: str
    name: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class CustomerProfile(BaseModel):
    id: int
    email: str
    name: str
    phone: Optional[str] = None
    clinic_name: Optional[str] = None
    gstin: Optional[str] = None
    billing_address: Optional[str] = None
    state: str
    city: Optional[str] = None
    pincode: Optional[str] = None

    class Config:
        from_attributes = True


class CustomerProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=8, max_length=20)
    clinic_name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    gstin: Optional[str] = Field(default=None, max_length=15)
    billing_address: Optional[str] = Field(default=None, min_length=5, max_length=500)
    state: Optional[str] = Field(default=None, min_length=2, max_length=100)
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    pincode: Optional[str] = Field(default=None, min_length=5, max_length=10)


class SubscriptionOut(BaseModel):
    id: int
    status: str
    billing_interval: str
    plan_name: str
    plan_slug: str
    clinic_name: Optional[str] = None
    current_period_start: datetime
    current_period_end: datetime
    amount: Decimal
    cancelled_at: Optional[datetime] = None
    cancel_at_period_end: bool = False

    class Config:
        from_attributes = True


class SubscriptionChangeRequest(BaseModel):
    plan_slug: str
    billing_interval: Literal["monthly", "yearly"] = "monthly"
    subscription_id: Optional[int] = None


class PlanChangePreviewResponse(BaseModel):
    current_plan_name: str
    current_plan_slug: str
    current_billing_interval: str
    new_plan_name: str
    new_plan_slug: str
    new_billing_interval: str
    days_remaining: int
    credit_amount: Decimal
    charge_amount: Decimal
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    is_intra_state: bool
    requires_payment: bool
    is_downgrade: bool
    interval_changed: bool
    same_selection: bool


class PlanChangeResponse(BaseModel):
    applied_immediately: bool
    message: str
    subscription: Optional[SubscriptionOut] = None
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    total: Optional[Decimal] = None
    payment_mode: Optional[str] = None
    razorpay_key_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    amount_paise: Optional[int] = None


class PlanChangeConfirmRequest(BaseModel):
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None


class ResubscribeRequest(BaseModel):
    plan_slug: str
    billing_interval: Literal["monthly", "yearly"] = "monthly"
    coupon_code: Optional[str] = Field(default=None, max_length=30)


class ResubscribePreviewResponse(BaseModel):
    plan_slug: str
    plan_name: str
    billing_interval: str
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    is_intra_state: bool
    discount_amount: Decimal = Decimal("0.00")
    coupon_code: Optional[str] = None
    trial_days: Optional[int] = None


class ResubscribeResponse(BaseModel):
    applied_immediately: bool
    message: str
    subscription: Optional[SubscriptionOut] = None
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    total: Optional[Decimal] = None
    payment_mode: Optional[str] = None
    razorpay_key_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    amount_paise: Optional[int] = None


class ReactivateResponse(BaseModel):
    subscription: SubscriptionOut
    message: str


class SubscriptionCancelResponse(BaseModel):
    subscription_id: int
    status: str
    current_period_end: datetime
    message: str


class AdminCommerceStats(BaseModel):
    total_customers: int
    active_subscriptions: int
    cancelled_subscriptions: int
    pending_orders: int
    total_revenue: Decimal
    mrr: Decimal
    new_contact_submissions: int


class RevenueMonthPoint(BaseModel):
    month: str
    month_key: str
    revenue: Decimal


class AdminCommerceAnalytics(BaseModel):
    revenue_series: list[RevenueMonthPoint]
    revenue_this_month: Decimal
    mrr: Decimal
    arpu: Decimal
    churn_rate_30d: Decimal
    subscription_status: dict[str, int]
    plan_distribution: dict[str, int]
    order_type_breakdown: dict[str, int]
    total_paid_invoices: int
    refunded_invoices: int


class RetryPaymentPreviewResponse(BaseModel):
    plan_slug: str
    plan_name: str
    billing_interval: str
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    is_intra_state: bool
    discount_amount: Decimal = Decimal("0")
    coupon_code: Optional[str] = None
    trial_days: Optional[int] = None


class RetryPaymentResponse(BaseModel):
    order_id: int
    order_number: str
    total: Decimal
    payment_mode: str
    razorpay_key_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    amount_paise: Optional[int] = None
    message: str


class AdminCustomerOut(BaseModel):
    id: int
    name: str
    email: str
    clinic_name: Optional[str] = None
    phone: Optional[str] = None
    state: str
    created_at: datetime
    active_plan: Optional[str] = None
    subscription_status: Optional[str] = None

    class Config:
        from_attributes = True


class AdminOrderOut(BaseModel):
    id: int
    order_number: str
    customer_email: str
    customer_name: str
    order_type: str = "checkout"
    status: str
    total: Decimal
    coupon_code: Optional[str] = None
    created_at: datetime


class AdminPaymentOut(BaseModel):
    id: int
    invoice_number: str
    customer_email: str
    total: Decimal
    status: str
    payment_method: str
    paid_at: Optional[datetime] = None


class AdminCustomerSubscriptionOut(BaseModel):
    id: int
    plan_name: str
    status: str
    billing_interval: str
    clinic_name: Optional[str] = None
    current_period_end: datetime
    amount: Decimal


class AdminCustomerDetailOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    clinic_name: Optional[str] = None
    billing_address: Optional[str] = None
    state: str
    city: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    created_at: datetime
    notify_email_billing: bool
    notify_email_marketing: bool
    notify_sms_billing: bool
    active_subscription: Optional[SubscriptionOut] = None
    billing_summary: Optional[BillingSummaryOut] = None
    subscriptions: list[AdminCustomerSubscriptionOut]
    recent_orders: list[AdminOrderOut]
    recent_payments: list[AdminPaymentOut]
    invoices: list[InvoiceOut] = []
    credit_notes: list[CustomerCreditNoteOut] = []
    total_spent: Decimal


class AdminSubscriptionOut(BaseModel):
    id: int
    customer_email: str
    customer_name: str
    plan_name: str
    billing_interval: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    amount: Decimal
    gateway_subscription_id: Optional[str] = None


class AdminSubscriptionExtendRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)


class AdminSubscriptionActionResponse(BaseModel):
    subscription_id: int
    status: str
    current_period_end: datetime
    message: str


class AdminSubscriptionRenewResponse(BaseModel):
    subscription_id: int
    subscription_status: str
    current_period_end: datetime
    payment_id: int
    invoice_number: str
    total: Decimal
    message: str


class AdminEmailLogOut(BaseModel):
    id: int
    template: str
    recipient: str
    subject: str
    status: str
    created_at: datetime


class AdminCouponOut(BaseModel):
    id: int
    code: str
    description: Optional[str] = None
    discount_type: str
    discount_value: Decimal
    billing_interval: Optional[str] = None
    trial_days: Optional[int] = None
    max_uses: Optional[int] = None
    used_count: int
    is_active: bool

    class Config:
        from_attributes = True


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    description: Optional[str] = Field(default=None, max_length=255)
    discount_type: Literal["percent", "fixed"] = "percent"
    discount_value: Decimal = Field(gt=0)
    billing_interval: Optional[Literal["monthly", "yearly"]] = None
    trial_days: Optional[int] = Field(default=None, ge=0, le=365)
    max_uses: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True


class CouponUpdateRequest(BaseModel):
    description: Optional[str] = Field(default=None, max_length=255)
    discount_type: Optional[Literal["percent", "fixed"]] = None
    discount_value: Optional[Decimal] = Field(default=None, gt=0)
    billing_interval: Optional[Literal["monthly", "yearly"]] = None
    trial_days: Optional[int] = Field(default=None, ge=0, le=365)
    max_uses: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None


class AdminCreditNoteOut(BaseModel):
    id: int
    credit_note_number: str
    customer_email: str
    customer_name: str
    invoice_number: str
    amount: Decimal
    reason: Optional[str] = None
    status: str
    created_at: datetime


class RefundRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class CreditNoteOut(BaseModel):
    id: int
    credit_note_number: str
    payment_id: int
    amount: Decimal
    reason: Optional[str] = None
    status: str
    pdf_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerCreditNoteOut(BaseModel):
    id: int
    credit_note_number: str
    invoice_number: str
    amount: Decimal
    reason: Optional[str] = None
    status: str
    pdf_path: Optional[str] = None
    created_at: datetime


class InvoiceOut(BaseModel):
    id: int
    invoice_number: str
    subscription_id: Optional[int] = None
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    status: str
    payment_method: str
    pdf_path: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
