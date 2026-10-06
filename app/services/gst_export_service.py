import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.payment import Payment


def build_gst_export_csv(db: Session) -> str:
    payments = (
        db.query(Payment)
        .options(joinedload(Payment.customer))
        .filter(Payment.status.in_(["paid", "refunded"]))
        .order_by(Payment.paid_at.asc(), Payment.created_at.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number",
        "Invoice Date",
        "Customer Name",
        "Customer Email",
        "Customer GSTIN",
        "Customer State",
        "Subtotal",
        "CGST",
        "SGST",
        "IGST",
        "GST Total",
        "Grand Total",
        "Status",
        "Payment Method",
    ])

    for payment in payments:
        customer: Customer | None = payment.customer
        paid_at = payment.paid_at or payment.created_at
        writer.writerow([
            payment.invoice_number,
            paid_at.strftime("%Y-%m-%d") if paid_at else "",
            customer.name if customer else "",
            customer.email if customer else "",
            customer.gstin if customer and customer.gstin else "",
            customer.state if customer else "",
            f"{payment.subtotal:.2f}",
            f"{payment.cgst:.2f}",
            f"{payment.sgst:.2f}",
            f"{payment.igst:.2f}",
            f"{payment.gst_total:.2f}",
            f"{payment.total:.2f}",
            payment.status,
            payment.payment_method,
        ])

    return output.getvalue()
