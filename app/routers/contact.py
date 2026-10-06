from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact_submission import ContactSubmission
from app.schemas.contact import ContactSubmissionRequest
from app.services.email_service import send_contact_admin_notification, send_contact_auto_reply

router = APIRouter(prefix="/contact", tags=["Contact"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_contact(payload: ContactSubmissionRequest, db: Session = Depends(get_db)):
    submission = ContactSubmission(
        full_name=payload.full_name.strip(),
        email=payload.email.lower().strip(),
        phone=payload.phone.strip(),
        clinic_name=payload.clinic_name.strip(),
        inquiry_type=payload.inquiry_type.strip(),
        message=payload.message.strip(),
        status="new",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    send_contact_auto_reply(db, submission_id=submission.id, name=submission.full_name, email=submission.email)
    send_contact_admin_notification(
        db,
        submission_id=submission.id,
        full_name=submission.full_name,
        email=submission.email,
        phone=submission.phone,
        clinic_name=submission.clinic_name,
        inquiry_type=submission.inquiry_type,
        message=submission.message,
    )
    db.commit()

    return {"message": "Thank you. Our team will get back to you within one business day."}
