from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.admin_auth import require_admin
from app.models.contact_submission import ContactSubmission
from app.schemas.contact import ContactSubmissionOut

router = APIRouter(prefix="/admin", tags=["Admin Contact"])


@router.get("/contact-submissions", response_model=list[ContactSubmissionOut], dependencies=[Depends(require_admin)])
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


@router.patch("/contact-submissions/{submission_id}/read", dependencies=[Depends(require_admin)])
def mark_contact_read(submission_id: int, db: Session = Depends(get_db)):
    submission = db.query(ContactSubmission).filter(ContactSubmission.id == submission_id).first()
    if submission:
        submission.status = "read"
        db.commit()
    return {"status": "ok"}
