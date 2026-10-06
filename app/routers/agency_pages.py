import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agency_page import AgencyPage
from app.schemas.agency_page import AgencyPageCreate, AgencyPageResponse, AgencyPageUpdate

router = APIRouter(prefix="/agency-pages", tags=["Agency Pages"])


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or f"page-{uuid4().hex[:8]}"


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("BLOG_ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


@router.get("/", response_model=list[AgencyPageResponse])
def get_published_agency_pages(
    page_type: str | None = Query(default=None, alias="type"),
    db: Session = Depends(get_db),
):
    query = db.query(AgencyPage).filter(AgencyPage.status == "published")
    if page_type in {"service", "project"}:
        query = query.filter(AgencyPage.page_type == page_type)
    return query.order_by(AgencyPage.sort_order.asc(), AgencyPage.created_at.desc()).all()


@router.get("/admin", response_model=list[AgencyPageResponse], dependencies=[Depends(require_admin)])
def get_admin_agency_pages(db: Session = Depends(get_db)):
    return db.query(AgencyPage).order_by(AgencyPage.sort_order.asc(), AgencyPage.created_at.desc()).all()


@router.get("/by-slug/{slug}", response_model=AgencyPageResponse)
def get_agency_page_by_slug(slug: str, db: Session = Depends(get_db)):
    page = db.query(AgencyPage).filter(AgencyPage.slug == slug).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/{slug}", response_model=AgencyPageResponse)
def get_agency_page(slug: str, db: Session = Depends(get_db)):
    if slug == "admin":
        raise HTTPException(status_code=404, detail="Page not found")
    page = db.query(AgencyPage).filter(AgencyPage.slug == slug).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.post("/", response_model=AgencyPageResponse, dependencies=[Depends(require_admin)])
def create_agency_page(payload: AgencyPageCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["slug"] = slugify(data["slug"] or data["title"])
    page = AgencyPage(**data)
    db.add(page)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A page with this slug already exists") from exc
    db.refresh(page)
    return page


@router.put("/{page_id}", response_model=AgencyPageResponse, dependencies=[Depends(require_admin)])
def update_agency_page(page_id: int, payload: AgencyPageUpdate, db: Session = Depends(get_db)):
    page = db.query(AgencyPage).filter(AgencyPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    elif "title" in data and data["title"] and not page.slug:
        data["slug"] = slugify(data["title"])

    for key, value in data.items():
        setattr(page, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A page with this slug already exists") from exc
    db.refresh(page)
    return page


@router.delete("/{page_id}", dependencies=[Depends(require_admin)])
def delete_agency_page(page_id: int, db: Session = Depends(get_db)):
    page = db.query(AgencyPage).filter(AgencyPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    db.delete(page)
    db.commit()
    return {"ok": True}
