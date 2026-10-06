import json
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.admin_auth import require_admin
from app.models.product_page import ProductPage
from app.schemas.product_page import (
    ProductPageCreate,
    ProductPageMegaMenuResponse,
    ProductPageMenuItem,
    ProductPageResponse,
    ProductPageUpdate,
)

router = APIRouter(prefix="/product-pages", tags=["Product Pages"])

CATEGORY_PATHS = {
    "apps-tools": "/apps-and-tools",
    "practice-types": "/practice-types",
    "multi-clinic": "/multi-clinic",
    "portfolio-applications": "/my-product",
    "portfolio-websites": "/my-product",
    "saas-product": "/products",
}

VALID_CATEGORIES = set(CATEGORY_PATHS.keys())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or f"product-page-{uuid4().hex[:8]}"


def page_order():
    return (
        ProductPage.category.asc(),
        ProductPage.sort_order.asc(),
        ProductPage.title.asc(),
    )


def public_link(page: ProductPage) -> str:
    if page.category == "saas-product":
        return f"/products/{page.slug}"
    if page.link:
        return page.link
    base = CATEGORY_PATHS.get(page.category, "/apps-and-tools")
    return f"{base}/{page.slug}"


def to_menu_item(page: ProductPage) -> ProductPageMenuItem:
    return ProductPageMenuItem(
        title=page.title,
        description=page.description,
        link=public_link(page),
        icon=page.icon,
    )


@router.get("/", response_model=list[ProductPageResponse])
def get_published_product_pages(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(ProductPage).filter(ProductPage.status == "published")
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        query = query.filter(ProductPage.category == category)
    return query.order_by(*page_order()).all()


@router.get("/mega-menu", response_model=ProductPageMegaMenuResponse)
def get_product_pages_mega_menu(db: Session = Depends(get_db)):
    pages = (
        db.query(ProductPage)
        .filter(ProductPage.status == "published")
        .order_by(*page_order())
        .all()
    )
    return ProductPageMegaMenuResponse(
        apps_tools=[to_menu_item(page) for page in pages if page.category == "apps-tools"],
        practice_types=[to_menu_item(page) for page in pages if page.category == "practice-types"],
        multi_clinic=[to_menu_item(page) for page in pages if page.category == "multi-clinic"],
    )


@router.get("/admin", response_model=list[ProductPageResponse], dependencies=[Depends(require_admin)])
def get_admin_product_pages(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(ProductPage)
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        query = query.filter(ProductPage.category == category)
    return query.order_by(*page_order()).all()


@router.post("/sync-seed", dependencies=[Depends(require_admin)])
def sync_product_pages_seed(db: Session = Depends(get_db)):
    from app.services.product_page_seed import SEED_DIR

    if not SEED_DIR.exists():
        raise HTTPException(status_code=404, detail="Product pages seed directory not found")

    created = 0
    updated = 0

    for seed_file in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        slug = payload.get("slug")
        if not slug:
            continue

        existing = db.query(ProductPage).filter(ProductPage.slug == slug).first()
        fields = {
            "category": payload["category"],
            "title": payload["title"],
            "description": payload.get("description"),
            "content": payload.get("content"),
            "icon": payload.get("icon"),
            "image": payload.get("image"),
            "link": payload.get("link"),
            "sort_order": payload.get("sort_order", 0),
            "status": payload.get("status", "published"),
            "meta_title": payload.get("meta_title"),
            "meta_description": payload.get("meta_description"),
            "meta_keywords": payload.get("meta_keywords"),
            "canonical_url": payload.get("canonical_url"),
            "og_image": payload.get("og_image"),
            "capabilities_json": payload.get("capabilities_json"),
            "saas_meta_json": payload.get("saas_meta_json"),
        }

        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            updated += 1
            continue

        db.add(ProductPage(slug=slug, **fields))
        created += 1

    db.commit()
    return {"message": "Product pages seed synced", "created": created, "updated": updated}


@router.get("/{slug}", response_model=ProductPageResponse)
def get_product_page(slug: str, db: Session = Depends(get_db)):
    page = (
        db.query(ProductPage)
        .filter(ProductPage.slug == slug, ProductPage.status == "published")
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="Product page not found")
    return page


@router.post("/", response_model=ProductPageResponse, dependencies=[Depends(require_admin)])
def create_product_page(payload: ProductPageCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["slug"] = slugify(data["slug"] or data["title"])
    page = ProductPage(**data)

    db.add(page)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A product page with this slug already exists") from exc

    db.refresh(page)
    return page


@router.put("/{page_id}", response_model=ProductPageResponse, dependencies=[Depends(require_admin)])
def update_product_page(page_id: int, payload: ProductPageUpdate, db: Session = Depends(get_db)):
    page = db.query(ProductPage).filter(ProductPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Product page not found")

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        data["slug"] = slugify(data["slug"])
    if "slug" in data and not data["slug"]:
        data.pop("slug")

    for key, value in data.items():
        setattr(page, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A product page with this slug already exists") from exc

    db.refresh(page)
    return page


@router.delete("/{page_id}", dependencies=[Depends(require_admin)])
def delete_product_page(page_id: int, db: Session = Depends(get_db)):
    page = db.query(ProductPage).filter(ProductPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Product page not found")

    db.delete(page)
    db.commit()
    return {"message": "Product page deleted"}
