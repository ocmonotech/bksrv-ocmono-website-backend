from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.payment import Payment
from app.services.commerce_utils import generate_credit_note_number, get_company_gstin, get_company_legal_name
from app.services.email_service import send_email


def _generate_credit_note_pdf(*, credit_note: CreditNote, payment: Payment, customer: Customer) -> str:
    uploads_root = Path(__file__).resolve().parents[2] / "uploads" / "credit-notes"
    uploads_root.mkdir(parents=True, exist_ok=True)
    filename = f"{credit_note.credit_note_number.replace('/', '-')}.pdf"
    output_path = uploads_root / filename

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, get_company_legal_name(), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"GSTIN: {get_company_gstin()}", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "CREDIT NOTE", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Credit Note No: {credit_note.credit_note_number}", ln=True)
    pdf.cell(0, 6, f"Against Invoice: {payment.invoice_number}", ln=True)
    pdf.cell(0, 6, f"Date: {datetime.now(timezone.utc).strftime('%d-%m-%Y')}", ln=True)
    pdf.ln(6)
    pdf.cell(0, 6, f"Customer: {customer.name}", ln=True)
    pdf.cell(0, 6, f"Email: {customer.email}", ln=True)
    pdf.ln(6)
    pdf.cell(0, 6, f"Refund amount: ₹ {Decimal(str(credit_note.amount)):,.2f}", ln=True)
    if credit_note.reason:
        pdf.multi_cell(0, 6, f"Reason: {credit_note.reason}")
    pdf.output(str(output_path))
    return f"credit-notes/{filename}"


def issue_refund(
    db: Session,
    *,
    payment: Payment,
    customer: Customer,
    reason: str | None = None,
) -> CreditNote:
    if payment.status != "paid":
        raise ValueError("Only paid invoices can be refunded")

    credit_note = CreditNote(
        credit_note_number=generate_credit_note_number(db),
        payment_id=payment.id,
        customer_id=customer.id,
        amount=payment.total,
        reason=reason or "Admin refund",
        status="issued",
    )
    db.add(credit_note)
    db.flush()

    credit_note.pdf_path = _generate_credit_note_pdf(credit_note=credit_note, payment=payment, customer=customer)
    payment.status = "refunded"
    db.commit()
    db.refresh(credit_note)

    html = f"""
    <h2>Refund processed</h2>
    <p>Hi {customer.name},</p>
    <p>A credit note <strong>{credit_note.credit_note_number}</strong> has been issued for invoice {payment.invoice_number}.</p>
    <p>Refund amount: <strong>₹ {payment.total}</strong></p>
    """
    send_email(
        db,
        customer_id=customer.id,
        template="credit_note",
        recipient=customer.email,
        subject=f"ClinicPro refund — {credit_note.credit_note_number}",
        html_body=html,
        reference_type="credit_note",
        reference_id=credit_note.id,
    )
    db.commit()
    return credit_note
