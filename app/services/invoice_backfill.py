from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.payment import Payment
from app.models.plan import Plan, PlanPrice
from app.services.invoice_pdf import generate_invoice_pdf


def backfill_invoice_pdfs(db: Session) -> None:
    payments = (
        db.query(Payment)
        .options(joinedload(Payment.order))
        .filter(Payment.pdf_path.is_(None), Payment.status == "paid")
        .all()
    )

    for payment in payments:
        order = payment.order
        if not order:
            continue

        plan_price = db.query(PlanPrice).filter(PlanPrice.id == order.plan_price_id).first()
        if not plan_price:
            continue

        plan = db.query(Plan).filter(Plan.id == plan_price.plan_id).first()
        customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
        if not plan or not customer:
            continue

        payment.pdf_path = generate_invoice_pdf(
            payment=payment,
            customer=customer,
            plan=plan,
            billing_interval=plan_price.billing_interval,
        )

    if payments:
        db.commit()
