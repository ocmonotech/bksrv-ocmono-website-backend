import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.product_page import ProductPage

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "product-pages"

PRODUCT_PAGE_FIELDS = (
    "category",
    "title",
    "description",
    "content",
    "icon",
    "image",
    "link",
    "sort_order",
    "status",
    "meta_title",
    "meta_description",
    "meta_keywords",
    "canonical_url",
    "og_image",
    "robots",
    "schema_json",
    "capabilities_json",
    "saas_meta_json",
)


def _payload_fields(payload: dict) -> dict:
    fields = {}
    for key in PRODUCT_PAGE_FIELDS:
        if key == "category":
            fields[key] = payload["category"]
            continue
        if key == "title":
            fields[key] = payload["title"]
            continue
        if key == "sort_order":
            fields[key] = payload.get("sort_order", 0)
            continue
        if key == "status":
            fields[key] = payload.get("status", "published")
            continue
        fields[key] = payload.get(key)
    return fields


def seed_product_pages(db: Session):
    """Insert missing seeded pages without overwriting edits made in admin."""
    if not SEED_DIR.exists():
        return

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        if db.query(ProductPage).filter(ProductPage.slug == slug).first():
            continue

        db.add(ProductPage(slug=slug, **_payload_fields(payload)))

    db.commit()
