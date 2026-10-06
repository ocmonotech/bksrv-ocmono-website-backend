import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.integration import Integration

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "integrations"


def seed_integrations(db: Session):
    if not SEED_DIR.exists():
        return

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(Integration).filter(Integration.slug == slug).first()
        if existing:
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

    db.commit()
