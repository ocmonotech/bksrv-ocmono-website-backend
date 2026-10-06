import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.profession import Profession

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "professions"


def seed_professions(db: Session):
    if not SEED_DIR.exists():
        return

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(Profession).filter(Profession.slug == slug).first()
        if existing:
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

    db.commit()
