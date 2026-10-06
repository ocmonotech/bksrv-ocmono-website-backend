from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact_submission import ContactSubmission
from app.schemas.demo_booking import DemoBookingRequest
from app.services.email_service import send_contact_admin_notification, send_demo_booking_confirmation

router = APIRouter(prefix="/demo-bookings", tags=["Demo bookings"])

INQUIRY_TYPE = "Demo booking"


def _build_message(payload: DemoBookingRequest) -> str:
    lines = [
        f"Preferred date: {payload.demo_date}",
        f"Preferred time: {payload.demo_time}",
    ]
    note = (payload.message or "").strip()
    if note:
        lines.append(f"Notes: {note}")
    return "\n".join(lines)


@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_demo_booking(payload: DemoBookingRequest, db: Session = Depends(get_db)):
    clinic_name = (payload.clinic_name or "").strip() or "Not specified"
    message = _build_message(payload)

    submission = ContactSubmission(
        full_name=payload.full_name.strip(),
        email=payload.email.lower().strip(),
        phone=payload.phone.strip(),
        clinic_name=clinic_name,
        inquiry_type=INQUIRY_TYPE,
        message=message,
        status="new",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    send_demo_booking_confirmation(
        db,
        submission_id=submission.id,
        name=submission.full_name,
        email=submission.email,
        demo_date=payload.demo_date,
        demo_time=payload.demo_time,
    )
    send_contact_admin_notification(
        db,
        submission_id=submission.id,
        full_name=submission.full_name,
        email=submission.email,
        phone=submission.phone,
        clinic_name=submission.clinic_name,
        inquiry_type=submission.inquiry_type,
        message=message,
    )
    db.commit()

    return {
        "message": "Demo request received. We'll confirm your slot within 24 hours.",
        "submission_id": submission.id,
    }
