import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.profession import Profession
from app.schemas.profession import (
    ProfessionCreate,
    ProfessionMegaMenuItem,
    ProfessionMegaMenuResponse,
    ProfessionResponse,
    ProfessionUpdate,
)

router = APIRouter(prefix="/professions", tags=["Professions"])

DEFAULT_FOOTER_LINKS = [
    {"title": "See All Health Clinics We Serve", "link": "/professions"},
    {"title": "Integrations", "link": "/integrations"},
    {"title": "Watch Demo", "link": "/contact"},
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or f"profession-{uuid4().hex[:8]}"


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("BLOG_ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def profession_order():
    return (
        Profession.mega_menu_column.asc(),
        Profession.sort_order.asc(),
        Profession.title.asc(),
    )


def profession_to_menu_item(profession: Profession) -> ProfessionMegaMenuItem:
    return ProfessionMegaMenuItem(
        title=profession.title,
        link=f"/professions/{profession.slug}",
    )


def build_mega_menu_columns(professions: list[Profession]) -> list[list[ProfessionMegaMenuItem]]:
    columns: list[list[ProfessionMegaMenuItem]] = [[], [], []]
    for profession in professions:
        column_index = min(max(profession.mega_menu_column, 0), 2)
        columns[column_index].append(profession_to_menu_item(profession))
    return columns


@router.get("/", response_model=list[ProfessionResponse])
def get_published_professions(db: Session = Depends(get_db)):
    return (
        db.query(Profession)
        .filter(Profession.status == "published")
        .order_by(*profession_order())
        .all()
    )


@router.get("/homepage", response_model=list[ProfessionResponse])
def get_homepage_professions(db: Session = Depends(get_db)):
    return (
        db.query(Profession)
        .filter(Profession.status == "published", Profession.show_on_homepage.is_(True))
        .order_by(Profession.sort_order.asc(), Profession.title.asc())
        .all()
    )


@router.get("/mega-menu", response_model=ProfessionMegaMenuResponse)
def get_professions_mega_menu(db: Session = Depends(get_db)):
    professions = (
        db.query(Profession)
        .filter(Profession.status == "published")
        .order_by(*profession_order())
        .all()
    )
    return ProfessionMegaMenuResponse(
        profession_columns=build_mega_menu_columns(professions),
        footer_links=[ProfessionMegaMenuItem(**link) for link in DEFAULT_FOOTER_LINKS],
    )


@router.get("/admin", response_model=list[ProfessionResponse], dependencies=[Depends(require_admin)])
def get_admin_professions(db: Session = Depends(get_db)):
    return db.query(Profession).order_by(*profession_order()).all()


@router.post("/sync-seed", dependencies=[Depends(require_admin)])
def sync_professions_seed(db: Session = Depends(get_db)):
    from app.services.profession_seed import SEED_DIR
    import json

    if not SEED_DIR.exists():
        raise HTTPException(status_code=404, detail="Professions seed directory not found")

    created = 0
    updated = 0

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(Profession).filter(Profession.slug == slug).first()
        if existing:
            existing.title = payload["title"]
            existing.description = payload.get("description")
            existing.content = payload.get("content")
            existing.image = payload.get("image")
            existing.mega_menu_column = payload.get("mega_menu_column", 0)
            existing.sort_order = payload.get("sort_order", 0)
            existing.show_on_homepage = bool(payload.get("show_on_homepage", False))
            existing.animation_delay = payload.get("animation_delay")
            existing.status = payload.get("status", "published")
            existing.meta_title = payload.get("meta_title")
            existing.meta_description = payload.get("meta_description")
            existing.meta_keywords = payload.get("meta_keywords")
            existing.canonical_url = payload.get("canonical_url")
            existing.og_image = payload.get("og_image")
            updated += 1
            continue

        profession = Profession(
            title=payload["title"],
            slug=slug,
            description=payload.get("description"),
            content=payload.get("content"),
            image=payload.get("image"),
            mega_menu_column=payload.get("mega_menu_column", 0),
            sort_order=payload.get("sort_order", 0),
            show_on_homepage=bool(payload.get("show_on_homepage", False)),
            animation_delay=payload.get("animation_delay"),
            status=payload.get("status", "published"),
            meta_title=payload.get("meta_title"),
            meta_description=payload.get("meta_description"),
            meta_keywords=payload.get("meta_keywords"),
            canonical_url=payload.get("canonical_url"),
            og_image=payload.get("og_image"),
        )
        db.add(profession)
        created += 1

    db.commit()
    return {"message": "Professions seed synced", "created": created, "updated": updated}


@router.get("/{slug}", response_model=ProfessionResponse)
def get_profession(slug: str, db: Session = Depends(get_db)):
    profession = (
        db.query(Profession)
        .filter(Profession.slug == slug, Profession.status == "published")
        .first()
    )
    if not profession:
        raise HTTPException(status_code=404, detail="Profession not found")
    return profession


@router.post("/", response_model=ProfessionResponse, dependencies=[Depends(require_admin)])
def create_profession(payload: ProfessionCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["slug"] = slugify(data["slug"] or data["title"])
    profession = Profession(**data)

    db.add(profession)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A profession with this slug already exists") from exc

    db.refresh(profession)
    return profession


@router.put("/{profession_id}", response_model=ProfessionResponse, dependencies=[Depends(require_admin)])
def update_profession(profession_id: int, payload: ProfessionUpdate, db: Session = Depends(get_db)):
    profession = db.query(Profession).filter(Profession.id == profession_id).first()
    if not profession:
        raise HTTPException(status_code=404, detail="Profession not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    if "slug" in data and not data["slug"]:
        data.pop("slug")

    for key, value in data.items():
        setattr(profession, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A profession with this slug already exists") from exc

    db.refresh(profession)
    return profession


@router.delete("/{profession_id}", dependencies=[Depends(require_admin)])
def delete_profession(profession_id: int, db: Session = Depends(get_db)):
    profession = db.query(Profession).filter(Profession.id == profession_id).first()
    if not profession:
        raise HTTPException(status_code=404, detail="Profession not found")

    db.delete(profession)
    db.commit()
    return {"message": "Profession deleted"}
