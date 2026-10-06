import json
import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.integration import Integration
from app.schemas.integration import IntegrationCreate, IntegrationResponse, IntegrationUpdate

router = APIRouter(prefix="/integrations", tags=["Integrations"])


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or f"integration-{uuid4().hex[:8]}"


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("BLOG_ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def integration_order():
    return (
        Integration.sort_order.asc(),
        Integration.title.asc(),
    )


@router.get("/", response_model=list[IntegrationResponse])
def get_published_integrations(db: Session = Depends(get_db)):
    return (
        db.query(Integration)
        .filter(Integration.status == "published")
        .order_by(*integration_order())
        .all()
    )


@router.get("/carousel", response_model=list[IntegrationResponse])
def get_carousel_integrations(db: Session = Depends(get_db)):
    return (
        db.query(Integration)
        .filter(Integration.status == "published", Integration.show_in_carousel.is_(True))
        .order_by(*integration_order())
        .all()
    )


@router.get("/admin", response_model=list[IntegrationResponse], dependencies=[Depends(require_admin)])
def get_admin_integrations(db: Session = Depends(get_db)):
    return db.query(Integration).order_by(*integration_order()).all()


@router.post("/sync-seed", dependencies=[Depends(require_admin)])
def sync_integrations_seed(db: Session = Depends(get_db)):
    from app.services.integration_seed import SEED_DIR

    if not SEED_DIR.exists():
        raise HTTPException(status_code=404, detail="Integrations seed directory not found")

    created = 0
    updated = 0

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(Integration).filter(Integration.slug == slug).first()
        if existing:
            existing.title = payload["title"]
            existing.description = payload.get("description")
            existing.content = payload.get("content")
            existing.logo = payload.get("logo")
            existing.category = payload.get("category", "General")
            existing.external_url = payload.get("external_url")
            existing.card_color = payload.get("card_color", 1)
            existing.sort_order = payload.get("sort_order", 0)
            existing.show_in_carousel = bool(payload.get("show_in_carousel", False))
            existing.status = payload.get("status", "published")
            existing.meta_title = payload.get("meta_title")
            existing.meta_description = payload.get("meta_description")
            existing.meta_keywords = payload.get("meta_keywords")
            existing.canonical_url = payload.get("canonical_url")
            existing.og_image = payload.get("og_image")
            updated += 1
            continue

        integration = Integration(
            title=payload["title"],
            slug=slug,
            description=payload.get("description"),
            content=payload.get("content"),
            logo=payload.get("logo"),
            category=payload.get("category", "General"),
            external_url=payload.get("external_url"),
            card_color=payload.get("card_color", 1),
            sort_order=payload.get("sort_order", 0),
            show_in_carousel=bool(payload.get("show_in_carousel", False)),
            status=payload.get("status", "published"),
            meta_title=payload.get("meta_title"),
            meta_description=payload.get("meta_description"),
            meta_keywords=payload.get("meta_keywords"),
            canonical_url=payload.get("canonical_url"),
            og_image=payload.get("og_image"),
        )
        db.add(integration)
        created += 1

    db.commit()
    return {"message": "Integrations seed synced", "created": created, "updated": updated}


@router.post("/", response_model=IntegrationResponse, dependencies=[Depends(require_admin)])
def create_integration(payload: IntegrationCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["slug"] = slugify(data["slug"] or data["title"])
    integration = Integration(**data)

    db.add(integration)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An integration with this slug already exists") from exc

    db.refresh(integration)
    return integration


@router.put("/{integration_id}", response_model=IntegrationResponse, dependencies=[Depends(require_admin)])
def update_integration(integration_id: int, payload: IntegrationUpdate, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    if "slug" in data and not data["slug"]:
        data.pop("slug")

    for key, value in data.items():
        setattr(integration, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An integration with this slug already exists") from exc

    db.refresh(integration)
    return integration


@router.delete("/{integration_id}", dependencies=[Depends(require_admin)])
def delete_integration(integration_id: int, db: Session = Depends(get_db)):
    integration = db.query(Integration).filter(Integration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    db.delete(integration)
    db.commit()
    return {"message": "Integration deleted"}
