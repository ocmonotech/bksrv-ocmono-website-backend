import csv
import io
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from uuid import uuid4

from app.database import get_db
from app.deps.admin_auth import require_admin
from app.models.blog import Blog
from app.models.chatbot import ChatbotSession
from app.models.contact_submission import ContactSubmission
from app.models.newsletter_subscriber import NewsletterSubscriber
from app.models.review import Review
from app.routers.seo import _build_content_catalog
from app.schemas.admin_dashboard import DashboardStatsResponse, MediaFileOut, NewsletterSubscriberOut

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/dashboard/stats", response_model=DashboardStatsResponse, dependencies=[Depends(require_admin)])
def dashboard_stats(db: Session = Depends(get_db)):
    catalog = _build_content_catalog(db)
    with_issues = sum(1 for item in catalog if item.issues)
    average_score = int(sum(item.score for item in catalog) / len(catalog)) if catalog else 100

    return DashboardStatsResponse(
        new_leads=db.query(ContactSubmission).filter(ContactSubmission.status == "new").count(),
        pending_reviews=db.query(Review).filter(Review.status == "pending").count(),
        newsletter_subscribers=db.query(NewsletterSubscriber)
        .filter(NewsletterSubscriber.status == "active")
        .count(),
        draft_blogs=db.query(Blog).filter(Blog.status == "draft").count(),
        chatbot_sessions=db.query(ChatbotSession)
        .filter(ChatbotSession.status != "archived")
        .count(),
        seo_total=len(catalog),
        seo_with_issues=with_issues,
        seo_average_score=average_score,
    )


@router.get(
    "/newsletter-subscribers",
    response_model=list[NewsletterSubscriberOut],
    dependencies=[Depends(require_admin)],
)
def list_newsletter_subscribers(db: Session = Depends(get_db)):
    subscribers = (
        db.query(NewsletterSubscriber).order_by(NewsletterSubscriber.created_at.desc()).limit(500).all()
    )
    return [
        NewsletterSubscriberOut(
            id=item.id,
            email=item.email,
            source=item.source,
            status=item.status,
            created_at=item.created_at.isoformat() if item.created_at else "",
        )
        for item in subscribers
    ]


@router.get("/contact-submissions/export", dependencies=[Depends(require_admin)])
def export_contact_submissions(db: Session = Depends(get_db)):
    submissions = (
        db.query(ContactSubmission).order_by(ContactSubmission.created_at.desc()).limit(5000).all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["ID", "Name", "Email", "Phone", "Company", "Service type", "Message", "Status", "Received"],
    )

    for item in submissions:
        writer.writerow(
            [
                item.id,
                item.full_name,
                item.email,
                item.phone or "",
                item.clinic_name or "",
                item.inquiry_type or "",
                (item.message or "").replace("\n", " "),
                item.status,
                item.created_at.isoformat() if item.created_at else "",
            ],
        )

    filename = f"ocmono-leads-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/media", response_model=list[MediaFileOut], dependencies=[Depends(require_admin)])
def list_media_files():
    public_api_url = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    files: list[MediaFileOut] = []

    for path in sorted(UPLOAD_DIR.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            MediaFileOut(
                filename=path.name,
                url=f"{public_api_url}/uploads/{path.name}",
                size=stat.st_size,
                modified_at=datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
            ),
        )

    return files


@router.post("/media", dependencies=[Depends(require_admin)])
async def upload_media_file(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed")

    suffix = Path(file.filename or "").suffix.lower()
    filename = f"{uuid4().hex}{suffix}"
    destination = UPLOAD_DIR / filename

    with destination.open("wb") as buffer:
        buffer.write(await file.read())

    public_api_url = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    stat = destination.stat()
    return MediaFileOut(
        filename=filename,
        url=f"{public_api_url}/uploads/{filename}",
        size=stat.st_size,
        modified_at=datetime.utcfromtimestamp(stat.st_mtime).isoformat(),
    )


@router.delete("/media/{filename}", dependencies=[Depends(require_admin)])
def delete_media_file(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target = UPLOAD_DIR / safe_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    target.unlink()
    return {"message": "File deleted"}
