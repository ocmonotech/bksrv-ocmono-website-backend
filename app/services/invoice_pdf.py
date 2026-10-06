import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from app.models.customer import Customer
from app.models.payment import Payment
from app.models.plan import Plan
from app.services.commerce_utils import get_company_gstin, get_company_legal_name, get_company_state


def _format_amount(value: Decimal | float) -> str:
    return f"₹ {Decimal(str(value)).quantize(Decimal('0.01')):,.2f}"


class InvoicePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, get_company_legal_name(), ln=True)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, f"GSTIN: {get_company_gstin()} | State: {get_company_state()}", ln=True)
        self.ln(4)


def generate_invoice_pdf(
    *,
    payment: Payment,
    customer: Customer,
    plan: Plan,
    billing_interval: str,
) -> str:
    uploads_root = Path(__file__).resolve().parents[2] / "uploads" / "invoices"
    uploads_root.mkdir(parents=True, exist_ok=True)

    filename = f"{payment.invoice_number.replace('/', '-')}.pdf"
    output_path = uploads_root / filename

    pdf = InvoicePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "TAX INVOICE", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Invoice No: {payment.invoice_number}", ln=True)
    paid_at = payment.paid_at or datetime.utcnow()
    pdf.cell(0, 6, f"Invoice Date: {paid_at.strftime('%d-%m-%Y')}", ln=True)
    pdf.cell(0, 6, "HSN/SAC: 998314 (Software as a Service)", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(95, 8, "Bill To", border=0)
    pdf.cell(95, 8, "Seller", border=0, ln=True)
    pdf.set_font("Helvetica", "", 10)

    buyer_lines = [
        customer.clinic_name or customer.name,
        customer.name,
        customer.billing_address or "",
        f"{customer.city or ''}, {customer.state} {customer.pincode or ''}".strip(", "),
        f"Email: {customer.email}",
        f"Phone: {customer.phone or '-'}",
    ]
    if customer.gstin:
        buyer_lines.append(f"GSTIN: {customer.gstin}")

    seller_lines = [
        get_company_legal_name(),
        f"GSTIN: {get_company_gstin()}",
        f"State: {get_company_state()}",
        "Email: billing@clinicpro.in",
    ]

    y_start = pdf.get_y()
    for line in buyer_lines:
        if line:
            pdf.cell(95, 6, line[:90], border=0)
            pdf.ln(6)
    buyer_end = pdf.get_y()

    pdf.set_xy(105, y_start)
    for line in seller_lines:
        pdf.cell(95, 6, line[:90], border=0, ln=True, align="L")

    pdf.set_y(max(buyer_end, pdf.get_y()) + 4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(90, 8, "Description", border=1)
    pdf.cell(30, 8, "Billing", border=1)
    pdf.cell(35, 8, "Taxable", border=1)
    pdf.cell(35, 8, "Total", border=1, ln=True)

    pdf.set_font("Helvetica", "", 10)
    description = f"ClinicPro {plan.name} Plan Subscription"
    pdf.cell(90, 8, description[:55], border=1)
    pdf.cell(30, 8, billing_interval.title(), border=1)
    pdf.cell(35, 8, _format_amount(payment.subtotal), border=1)
    pdf.cell(35, 8, _format_amount(payment.total), border=1, ln=True)

    pdf.ln(4)
    pdf.cell(0, 6, f"Subtotal: {_format_amount(payment.subtotal)}", ln=True)
    if Decimal(str(payment.cgst)) > 0:
        pdf.cell(0, 6, f"CGST (9%): {_format_amount(payment.cgst)}", ln=True)
    if Decimal(str(payment.sgst)) > 0:
        pdf.cell(0, 6, f"SGST (9%): {_format_amount(payment.sgst)}", ln=True)
    if Decimal(str(payment.igst)) > 0:
        pdf.cell(0, 6, f"IGST (18%): {_format_amount(payment.igst)}", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Grand Total: {_format_amount(payment.total)}", ln=True)

    pdf.ln(8)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(
        0,
        5,
        "This is a computer-generated GST invoice. Payment received electronically. "
        "Place of supply is based on the buyer billing state.",
    )

    pdf.output(str(output_path))
    return f"invoices/{filename}"
