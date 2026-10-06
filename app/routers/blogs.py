import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.blog import Blog
from app.schemas.blog import BlogCreate, BlogResponse, BlogUpdate

router = APIRouter(prefix="/blogs", tags=["Blogs"])
upload_router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or f"blog-{uuid4().hex[:8]}"


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("BLOG_ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def apply_publish_defaults(blog: Blog):
    if blog.status == "published" and blog.published_at is None:
        blog.published_at = datetime.utcnow()
    if blog.status == "draft":
        blog.published_at = None


@router.get("/", response_model=list[BlogResponse])
def get_published_blogs(db: Session = Depends(get_db)):
    return (
        db.query(Blog)
        .filter(Blog.status == "published")
        .order_by(Blog.published_at.desc(), Blog.created_at.desc())
        .all()
    )


@router.get("/admin", response_model=list[BlogResponse], dependencies=[Depends(require_admin)])
def get_admin_blogs(db: Session = Depends(get_db)):
    return db.query(Blog).order_by(Blog.created_at.desc()).all()


@router.get("/{slug}", response_model=BlogResponse)
def get_blog(slug: str, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.slug == slug).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog


@router.post("/", response_model=BlogResponse, dependencies=[Depends(require_admin)])
def create_blog(payload: BlogCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["slug"] = slugify(data["slug"] or data["title"])
    blog = Blog(**data)
    apply_publish_defaults(blog)

    db.add(blog)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A blog with this slug already exists") from exc

    db.refresh(blog)
    return blog


@router.put("/{blog_id}", response_model=BlogResponse, dependencies=[Depends(require_admin)])
def update_blog(blog_id: int, payload: BlogUpdate, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    if "slug" in data and not data["slug"]:
        data.pop("slug")

    for key, value in data.items():
        setattr(blog, key, value)

    apply_publish_defaults(blog)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A blog with this slug already exists") from exc

    db.refresh(blog)
    return blog


@router.delete("/{blog_id}", dependencies=[Depends(require_admin)])
def delete_blog(blog_id: int, db: Session = Depends(get_db)):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    db.delete(blog)
    db.commit()
    return {"message": "Blog deleted"}


@upload_router.post("", dependencies=[Depends(require_admin)])
async def upload_file(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are allowed")

    suffix = Path(file.filename or "").suffix.lower()
    filename = f"{uuid4().hex}{suffix}"
    destination = UPLOAD_DIR / filename

    with destination.open("wb") as buffer:
        buffer.write(await file.read())

    public_api_url = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    return {"url": f"{public_api_url}/uploads/{filename}"}
