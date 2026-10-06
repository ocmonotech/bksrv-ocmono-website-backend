import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.content_block import ContentBlock

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"

# Upsert these on every startup so dual-pillar site content lands in DB (Drupal-like defaults).
FORCE_UPSERT_SLUGS = {"homepage", "navigation", "about-page"}


def _merge_features_from_seed(db: Session) -> None:
    """Ensure features content includes every seeded feature id (adds missing only)."""
    seed_path = SEED_DIR / "features.json"
    if not seed_path.exists():
        return

    seed_features = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(seed_features, list):
        return

    block = db.query(ContentBlock).filter(ContentBlock.slug == "features").first()
    if not block:
        db.add(ContentBlock(slug="features", data=seed_features))
        return

    current = block.data if isinstance(block.data, list) else []
    existing_ids = {item.get("id") for item in current if isinstance(item, dict)}
    missing = [item for item in seed_features if isinstance(item, dict) and item.get("id") not in existing_ids]
    if not missing:
        return

    block.data = [*current, *missing]


def seed_content_blocks(db: Session):
    """Load top-level seed/*.json files into content_blocks (Drupal-like content types)."""
    if not SEED_DIR.exists():
        return

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        slug = seed_file.stem
        if slug == "features":
            continue

        data = json.loads(seed_file.read_text(encoding="utf-8"))
        existing = db.query(ContentBlock).filter(ContentBlock.slug == slug).first()

        if existing:
            if slug in FORCE_UPSERT_SLUGS:
                existing.data = data
            continue

        db.add(ContentBlock(slug=slug, data=data))

    _merge_features_from_seed(db)
    db.commit()
