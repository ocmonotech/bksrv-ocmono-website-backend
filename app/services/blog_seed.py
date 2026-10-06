import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.models.blog import Blog

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "blogs"

SEO_COLUMNS = [
    ("meta_title", "VARCHAR(255) NULL"),
    ("meta_description", "TEXT NULL"),
    ("meta_keywords", "VARCHAR(500) NULL"),
    ("canonical_url", "VARCHAR(500) NULL"),
    ("og_image", "VARCHAR(500) NULL"),
    ("schema_json", "JSON NULL"),
]


def _column_exists(connection, column_name: str) -> bool:
    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'blogs'
              AND COLUMN_NAME = :column_name
            """
        ),
        {"column_name": column_name},
    ).scalar()
    return bool(result)


def migrate_blog_seo_columns():
    with engine.begin() as connection:
        for column_name, column_type in SEO_COLUMNS:
            if _column_exists(connection, column_name):
                continue
            connection.execute(text(f"ALTER TABLE blogs ADD COLUMN {column_name} {column_type}"))


def _parse_datetime(value: str | None):
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1]
    return datetime.fromisoformat(value)


def seed_blogs(db: Session):
    if not SEED_DIR.exists():
        return

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(Blog).filter(Blog.slug == slug).first()
        if existing:
            continue

        blog = Blog(
            title=payload["title"],
            slug=slug,
            excerpt=payload.get("excerpt"),
            content=payload["content"],
            cover_image=payload.get("cover_image"),
            author=payload.get("author"),
            category=payload.get("category", "Resources"),
            status=payload.get("status", "published"),
            published_at=_parse_datetime(payload.get("published_at")),
            meta_title=payload.get("meta_title"),
            meta_description=payload.get("meta_description"),
            meta_keywords=payload.get("meta_keywords"),
            canonical_url=payload.get("canonical_url"),
            og_image=payload.get("og_image"),
            schema_json=payload.get("schema_json"),
        )
        if blog.status == "published" and blog.published_at is None:
            blog.published_at = datetime.utcnow()

        db.add(blog)

    db.commit()


def sync_blogs_from_seed(db: Session):
    """Refresh seeded blog media/content when seed files change."""
    if not SEED_DIR.exists():
        return

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(Blog).filter(Blog.slug == slug).first()
        if not existing:
            continue

        existing.content = payload["content"]
        existing.cover_image = payload.get("cover_image")
        existing.og_image = payload.get("og_image")
        if payload.get("schema_json") is not None:
            existing.schema_json = payload.get("schema_json")

    db.commit()
