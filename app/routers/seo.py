from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.admin_auth import require_admin
from app.models.agency_page import AgencyPage
from app.models.blog import Blog
from app.models.seo import SeoPage, SeoRedirect, SeoSiteSettings
from app.schemas.seo import (
    SeoAuditItem,
    SeoAuditResponse,
    SeoContentItem,
    SeoContentListResponse,
    SeoContentUpdate,
    SeoPageCreate,
    SeoPageResponse,
    SeoPageUpdate,
    SeoRedirectCreate,
    SeoRedirectResponse,
    SeoRedirectUpdate,
    SeoRobotsResponse,
    SeoSitemapEntry,
    SeoSitemapResponse,
    SeoSiteSettingsResponse,
    SeoSiteSettingsUpdate,
)
from app.services.seo_migrate import seed_seo_defaults

router = APIRouter(prefix="/seo", tags=["SEO"])

ENTITY_EDIT_HREFS = {
    "page": "/admin/seo?tab=pages&id={id}",
    "blog": "/admin/blogs/{id}/edit",
    "agency_page": "/admin/agency-pages/{id}/edit",
}

SEO_ONLY_FIELDS = (
    "meta_title",
    "meta_description",
    "meta_keywords",
    "canonical_url",
    "og_image",
    "robots",
    "schema_json",
)


def _normalize_path(path: str) -> str:
    value = (path or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Path is required")
    if not value.startswith("/"):
        value = f"/{value}"
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def _agency_page_path(page: AgencyPage) -> str:
    if page.page_type == "project":
        return f"/work/{page.slug}"
    return f"/services/{page.slug}"


def _get_or_create_settings(db: Session) -> SeoSiteSettings:
    settings = db.query(SeoSiteSettings).first()
    if settings:
        return settings
    seed_seo_defaults(db)
    settings = db.query(SeoSiteSettings).first()
    if not settings:
        raise HTTPException(status_code=500, detail="Failed to initialize SEO settings")
    return settings


def _score_issues(issues: list[str]) -> int:
    return max(0, 100 - (len(issues) * 20))


def _check_entity_seo(*, title: str, meta_title, meta_description, canonical_url, og_image) -> list[str]:
    issues: list[str] = []
    if not meta_title:
        issues.append("Missing meta title")
    elif len(meta_title) > 60:
        issues.append("Meta title longer than 60 characters")
    if not meta_description:
        issues.append("Missing meta description")
    elif len(meta_description) > 160:
        issues.append("Meta description longer than 160 characters")
    if not canonical_url:
        issues.append("Missing canonical URL")
    if not og_image:
        issues.append("Missing Open Graph image")
    if not title:
        issues.append("Missing title")
    return issues


def _content_item(
    *,
    entity_type: str,
    entity_id: int,
    title: str,
    path: str,
    status: str | None,
    meta_title,
    meta_description,
    meta_keywords,
    canonical_url,
    og_image,
    robots=None,
    schema_json=None,
) -> SeoContentItem:
    issues = _check_entity_seo(
        title=title,
        meta_title=meta_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        og_image=og_image,
    )
    edit_template = ENTITY_EDIT_HREFS.get(entity_type)
    return SeoContentItem(
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        path=path,
        status=status,
        edit_href=edit_template.format(id=entity_id) if edit_template else None,
        meta_title=meta_title,
        meta_description=meta_description,
        meta_keywords=meta_keywords,
        canonical_url=canonical_url,
        og_image=og_image,
        robots=robots,
        schema_json=schema_json,
        issues=issues,
        score=_score_issues(issues),
    )


def _build_content_catalog(db: Session) -> list[SeoContentItem]:
    items: list[SeoContentItem] = []

    for page in db.query(SeoPage).order_by(SeoPage.path.asc()).all():
        items.append(
            _content_item(
                entity_type="page",
                entity_id=page.id,
                title=page.label or page.path,
                path=page.path,
                status="managed",
                meta_title=page.meta_title,
                meta_description=page.meta_description,
                meta_keywords=page.meta_keywords,
                canonical_url=page.canonical_url or page.path,
                og_image=page.og_image,
                robots=page.robots,
                schema_json=page.schema_json,
            )
        )

    for blog in db.query(Blog).order_by(Blog.title.asc()).all():
        items.append(
            _content_item(
                entity_type="blog",
                entity_id=blog.id,
                title=blog.title,
                path=f"/blog/{blog.slug}",
                status=blog.status,
                meta_title=blog.meta_title,
                meta_description=blog.meta_description,
                meta_keywords=blog.meta_keywords,
                canonical_url=blog.canonical_url,
                og_image=blog.og_image or blog.cover_image,
                robots=getattr(blog, "robots", None),
                schema_json=blog.schema_json,
            )
        )

    for agency_page in db.query(AgencyPage).order_by(AgencyPage.title.asc()).all():
        path = agency_page.canonical_url or _agency_page_path(agency_page)
        items.append(
            _content_item(
                entity_type="agency_page",
                entity_id=agency_page.id,
                title=agency_page.title,
                path=path,
                status=agency_page.status,
                meta_title=agency_page.meta_title,
                meta_description=agency_page.meta_description,
                meta_keywords=agency_page.meta_keywords,
                canonical_url=agency_page.canonical_url or path,
                og_image=agency_page.og_image or agency_page.cover_image,
                robots=getattr(agency_page, "robots", None),
                schema_json=None,
            )
        )

    return items


def _get_entity(db: Session, entity_type: str, entity_id: int):
    if entity_type == "page":
        return db.query(SeoPage).filter(SeoPage.id == entity_id).first()
    if entity_type == "blog":
        return db.query(Blog).filter(Blog.id == entity_id).first()
    if entity_type == "agency_page":
        return db.query(AgencyPage).filter(AgencyPage.id == entity_id).first()
    raise HTTPException(status_code=400, detail="Unsupported entity type")


def _entity_to_content_item(db: Session, entity_type: str, entity) -> SeoContentItem:
    catalog = _build_content_catalog(db)
    for item in catalog:
        if item.entity_type == entity_type and item.entity_id == entity.id:
            return item
    raise HTTPException(status_code=404, detail="SEO content item not found")


@router.get("/settings", response_model=SeoSiteSettingsResponse)
def get_seo_settings(db: Session = Depends(get_db)):
    return _get_or_create_settings(db)


@router.put(
    "/settings",
    response_model=SeoSiteSettingsResponse,
    dependencies=[Depends(require_admin)],
)
def update_seo_settings(payload: SeoSiteSettingsUpdate, db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/pages", response_model=list[SeoPageResponse])
def list_seo_pages(db: Session = Depends(get_db)):
    _get_or_create_settings(db)
    return db.query(SeoPage).order_by(SeoPage.path.asc()).all()


@router.get("/pages/by-path")
def get_seo_page_by_path(path: str, db: Session = Depends(get_db)):
    normalized = _normalize_path(path)
    page = db.query(SeoPage).filter(SeoPage.path == normalized).first()
    if not page:
        return None
    return SeoPageResponse.model_validate(page)


@router.post(
    "/pages",
    response_model=SeoPageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_seo_page(payload: SeoPageCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["path"] = _normalize_path(data["path"])
    page = SeoPage(**data)
    db.add(page)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A SEO page with this path already exists")
    db.refresh(page)
    return page


@router.put(
    "/pages/{page_id}",
    response_model=SeoPageResponse,
    dependencies=[Depends(require_admin)],
)
def update_seo_page(page_id: int, payload: SeoPageUpdate, db: Session = Depends(get_db)):
    page = db.query(SeoPage).filter(SeoPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="SEO page not found")
    data = payload.model_dump(exclude_unset=True)
    if "path" in data and data["path"] is not None:
        data["path"] = _normalize_path(data["path"])
    for key, value in data.items():
        setattr(page, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A SEO page with this path already exists")
    db.refresh(page)
    return page


@router.delete("/pages/{page_id}", dependencies=[Depends(require_admin)])
def delete_seo_page(page_id: int, db: Session = Depends(get_db)):
    page = db.query(SeoPage).filter(SeoPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="SEO page not found")
    db.delete(page)
    db.commit()
    return {"ok": True}


@router.get("/redirects", response_model=list[SeoRedirectResponse])
def list_redirects(db: Session = Depends(get_db)):
    return db.query(SeoRedirect).order_by(SeoRedirect.from_path.asc()).all()


@router.get("/redirects/active", response_model=list[SeoRedirectResponse])
def list_active_redirects(db: Session = Depends(get_db)):
    return (
        db.query(SeoRedirect)
        .filter(SeoRedirect.is_active.is_(True))
        .order_by(SeoRedirect.from_path.asc())
        .all()
    )


@router.post(
    "/redirects",
    response_model=SeoRedirectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_redirect(payload: SeoRedirectCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["from_path"] = _normalize_path(data["from_path"])
    redirect = SeoRedirect(**data)
    db.add(redirect)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A redirect from this path already exists")
    db.refresh(redirect)
    return redirect


@router.put(
    "/redirects/{redirect_id}",
    response_model=SeoRedirectResponse,
    dependencies=[Depends(require_admin)],
)
def update_redirect(redirect_id: int, payload: SeoRedirectUpdate, db: Session = Depends(get_db)):
    redirect = db.query(SeoRedirect).filter(SeoRedirect.id == redirect_id).first()
    if not redirect:
        raise HTTPException(status_code=404, detail="Redirect not found")
    data = payload.model_dump(exclude_unset=True)
    if "from_path" in data and data["from_path"] is not None:
        data["from_path"] = _normalize_path(data["from_path"])
    for key, value in data.items():
        setattr(redirect, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A redirect from this path already exists")
    db.refresh(redirect)
    return redirect


@router.delete("/redirects/{redirect_id}", dependencies=[Depends(require_admin)])
def delete_redirect(redirect_id: int, db: Session = Depends(get_db)):
    redirect = db.query(SeoRedirect).filter(SeoRedirect.id == redirect_id).first()
    if not redirect:
        raise HTTPException(status_code=404, detail="Redirect not found")
    db.delete(redirect)
    db.commit()
    return {"ok": True}


@router.get("/content", response_model=SeoContentListResponse, dependencies=[Depends(require_admin)])
def list_seo_content(db: Session = Depends(get_db)):
    _get_or_create_settings(db)
    return SeoContentListResponse(items=_build_content_catalog(db))


@router.get(
    "/content/{entity_type}/{entity_id}",
    response_model=SeoContentItem,
    dependencies=[Depends(require_admin)],
)
def get_seo_content(entity_type: str, entity_id: int, db: Session = Depends(get_db)):
    entity = _get_entity(db, entity_type, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Content not found")
    return _entity_to_content_item(db, entity_type, entity)


@router.put(
    "/content/{entity_type}/{entity_id}",
    response_model=SeoContentItem,
    dependencies=[Depends(require_admin)],
)
def update_seo_content(
    entity_type: str,
    entity_id: int,
    payload: SeoContentUpdate,
    db: Session = Depends(get_db),
):
    entity = _get_entity(db, entity_type, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Content not found")

    data = payload.model_dump(exclude_unset=True)
    for key in SEO_ONLY_FIELDS:
        if key in data and hasattr(entity, key):
            setattr(entity, key, data[key])

    db.commit()
    db.refresh(entity)
    return _entity_to_content_item(db, entity_type, entity)


@router.get("/audit", response_model=SeoAuditResponse, dependencies=[Depends(require_admin)])
def seo_audit(db: Session = Depends(get_db)):
    catalog = _build_content_catalog(db)
    items = [
        SeoAuditItem(
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            title=item.title,
            path=item.path,
            status=item.status,
            issues=item.issues,
            score=item.score,
        )
        for item in catalog
    ]

    with_issues = sum(1 for item in items if item.issues)
    perfect = sum(1 for item in items if not item.issues)
    summary = {
        "total": len(items),
        "with_issues": with_issues,
        "perfect": perfect,
        "average_score": int(sum(item.score for item in items) / len(items)) if items else 100,
    }
    items.sort(key=lambda item: (len(item.issues) == 0, item.score, item.title))
    return SeoAuditResponse(summary=summary, items=items)


@router.get("/sitemap-data", response_model=SeoSitemapResponse)
def sitemap_data(db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    if not settings.sitemap_enabled:
        return SeoSitemapResponse(enabled=False, entries=[])

    entries: list[SeoSitemapEntry] = []

    for page in db.query(SeoPage).filter(SeoPage.sitemap_include.is_(True)).all():
        priority = None
        try:
            priority = float(page.sitemap_priority) if page.sitemap_priority else None
        except (TypeError, ValueError):
            priority = 0.7
        entries.append(
            SeoSitemapEntry(
                path=page.path,
                lastmod=page.updated_at,
                changefreq=page.sitemap_changefreq or "weekly",
                priority=priority,
            )
        )

    for blog in db.query(Blog).filter(Blog.status == "published").all():
        entries.append(
            SeoSitemapEntry(
                path=blog.canonical_url or f"/blog/{blog.slug}",
                lastmod=blog.updated_at or blog.published_at,
                changefreq="weekly",
                priority=0.6,
            )
        )

    for agency_page in db.query(AgencyPage).filter(AgencyPage.status == "published").all():
        entries.append(
            SeoSitemapEntry(
                path=agency_page.canonical_url or _agency_page_path(agency_page),
                lastmod=agency_page.updated_at,
                changefreq="monthly",
                priority=0.6,
            )
        )

    # Deduplicate by path (prefer first occurrence)
    seen: set[str] = set()
    unique: list[SeoSitemapEntry] = []
    for entry in entries:
        path = entry.path if entry.path.startswith("/") or entry.path.startswith("http") else f"/{entry.path}"
        key = path
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)

    return SeoSitemapResponse(enabled=True, entries=unique)


@router.get("/robots-data", response_model=SeoRobotsResponse)
def robots_data(db: Session = Depends(get_db)):
    settings = _get_or_create_settings(db)
    return SeoRobotsResponse(
        sitemap_enabled=settings.sitemap_enabled,
        robots_default=settings.robots_default,
        robots_extra=settings.robots_extra,
        disallow_paths=[
            "/admin",
            "/api",
            "/home-2",
            "/home-3",
            "/home-4",
            "/home-5",
            "/service",
            "/service-details",
            "/project",
            "/project-details",
            "/blog-list",
            "/blog-details",
            "/blog-details-2",
            "/career",
            "/career-details",
            "/team",
            "/team-details",
        ],
    )
