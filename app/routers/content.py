import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_block import ContentBlock
from app.schemas.content import ContentBlockCreate, ContentBlockResponse, ContentBlockUpdate
from app.schemas.feature import validate_features_content

router = APIRouter(prefix="/content", tags=["Content"])


def require_admin(x_admin_token: str | None = Header(default=None)):
    expected = os.getenv("BLOG_ADMIN_TOKEN")
    if expected and x_admin_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


@router.get("/", response_model=list[ContentBlockResponse])
def list_content_blocks(db: Session = Depends(get_db)):
    return db.query(ContentBlock).order_by(ContentBlock.slug.asc()).all()


@router.get("/{slug}", response_model=ContentBlockResponse)
def get_content_block(slug: str, db: Session = Depends(get_db)):
    block = db.query(ContentBlock).filter(ContentBlock.slug == slug).first()
    if not block:
        raise HTTPException(status_code=404, detail="Content block not found")
    return block


def normalize_content_data(slug: str, data):
    if slug == "features":
        try:
            return validate_features_content(data)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return data


@router.post("/", response_model=ContentBlockResponse, dependencies=[Depends(require_admin)])
def create_content_block(payload: ContentBlockCreate, db: Session = Depends(get_db)):
    existing = db.query(ContentBlock).filter(ContentBlock.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Content block with this slug already exists")

    block = ContentBlock(slug=payload.slug, data=normalize_content_data(payload.slug, payload.data))
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.put("/{slug}", response_model=ContentBlockResponse, dependencies=[Depends(require_admin)])
def update_content_block(slug: str, payload: ContentBlockUpdate, db: Session = Depends(get_db)):
    block = db.query(ContentBlock).filter(ContentBlock.slug == slug).first()
    data = normalize_content_data(slug, payload.data)

    if not block:
        block = ContentBlock(slug=slug, data=data)
        db.add(block)
    else:
        block.data = data

    db.commit()
    db.refresh(block)
    return block


@router.delete("/{slug}", dependencies=[Depends(require_admin)])
def delete_content_block(slug: str, db: Session = Depends(get_db)):
    block = db.query(ContentBlock).filter(ContentBlock.slug == slug).first()
    if not block:
        raise HTTPException(status_code=404, detail="Content block not found")

    db.delete(block)
    db.commit()
    return {"message": "Content block deleted"}


@router.post("/{slug}/sync-seed", response_model=ContentBlockResponse, dependencies=[Depends(require_admin)])
def sync_content_block_seed(slug: str, db: Session = Depends(get_db)):
    seed_path = Path(__file__).resolve().parents[2] / "seed" / f"{slug}.json"
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail=f"Seed file not found for slug '{slug}'")

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    data = normalize_content_data(slug, data)

    block = db.query(ContentBlock).filter(ContentBlock.slug == slug).first()
    if block:
        block.data = data
    else:
        block = ContentBlock(slug=slug, data=data)
        db.add(block)

    db.commit()
    db.refresh(block)
    return block

