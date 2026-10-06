import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.review import Review
from app.schemas.review import ReviewResponse, ReviewStatusUpdate, ReviewSubmission

router = APIRouter(prefix="/reviews", tags=["Reviews"])


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("BLOG_ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


@router.get("/", response_model=list[ReviewResponse])
def get_public_reviews(db: Session = Depends(get_db)):
    return (
        db.query(Review)
        .filter(Review.status == "approved")
        .order_by(Review.published_at.desc(), Review.created_at.desc())
        .limit(6)
        .all()
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_review(payload: ReviewSubmission, db: Session = Depends(get_db)):
    if not payload.consent_given:
        raise HTTPException(status_code=400, detail="Publishing consent is required")

    review = Review(**payload.model_dump(), source="testimonial", status="pending")
    db.add(review)
    db.commit()
    return {"message": "Thank you. Your feedback has been submitted for review."}


@router.get("/admin", response_model=list[ReviewResponse], dependencies=[Depends(require_admin)])
def get_admin_reviews(db: Session = Depends(get_db)):
    return db.query(Review).order_by(Review.created_at.desc()).all()


@router.patch("/{review_id}/status", response_model=ReviewResponse, dependencies=[Depends(require_admin)])
def update_review_status(review_id: int, payload: ReviewStatusUpdate, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = payload.status
    review.published_at = datetime.utcnow() if payload.status == "approved" else None
    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}", dependencies=[Depends(require_admin)])
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    db.delete(review)
    db.commit()
    return {"message": "Review deleted"}
