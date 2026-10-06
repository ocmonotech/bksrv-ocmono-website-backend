from decimal import Decimal
from typing import TypedDict


GST_RATE = Decimal("0.18")


class GstBreakdown(TypedDict):
    subtotal: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    is_intra_state: bool


def _normalize_state(state: str) -> str:
    return (state or "").strip().lower()


def calculate_gst(subtotal: Decimal | float, customer_state: str, company_state: str) -> GstBreakdown:
    amount = Decimal(str(subtotal)).quantize(Decimal("0.01"))
    gst_total = (amount * GST_RATE).quantize(Decimal("0.01"))
    is_intra_state = _normalize_state(customer_state) == _normalize_state(company_state)

    if is_intra_state:
        half = (gst_total / 2).quantize(Decimal("0.01"))
        cgst = half
        sgst = gst_total - half
        igst = Decimal("0.00")
    else:
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = gst_total

    total = (amount + gst_total).quantize(Decimal("0.01"))

    return {
        "subtotal": amount,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "gst_total": gst_total,
        "total": total,
        "is_intra_state": is_intra_state,
    }
