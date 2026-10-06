from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.newsletter_subscriber import NewsletterSubscriber
from app.schemas.newsletter import NewsletterSubscribeRequest, NewsletterSubscribeResponse
from app.services.email_service import send_newsletter_subscribe_confirmation

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])


@router.post("/subscribe", status_code=status.HTTP_201_CREATED, response_model=NewsletterSubscribeResponse)
def subscribe_newsletter(payload: NewsletterSubscribeRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    source = (payload.source or "website").strip()[:40] or "website"

    subscriber = db.query(NewsletterSubscriber).filter(NewsletterSubscriber.email == email).first()

    if not subscriber:
        subscriber = NewsletterSubscriber(email=email, source=source, status="active")
        db.add(subscriber)
        db.commit()
        db.refresh(subscriber)
    elif subscriber.status != "active":
        subscriber.status = "active"
        subscriber.source = source
        db.commit()
        db.refresh(subscriber)

    send_newsletter_subscribe_confirmation(db, subscriber_id=subscriber.id, email=email)
    db.commit()

    return NewsletterSubscribeResponse(
        message="You're subscribed to the OCMONO newsletter. Check your inbox for a confirmation email.",
        email=email,
    )
