from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine
from app.models.seo import SeoPage, SeoSiteSettings

OCMONO_DEFAULT_PAGES = [
    {"path": "/", "label": "Home", "sitemap_priority": "1.0", "sitemap_changefreq": "daily"},
    {"path": "/about", "label": "About", "sitemap_priority": "0.7", "sitemap_changefreq": "monthly"},
    {"path": "/services", "label": "Services", "sitemap_priority": "0.9", "sitemap_changefreq": "weekly"},
    {"path": "/products", "label": "Products", "sitemap_priority": "0.9", "sitemap_changefreq": "weekly"},
    {"path": "/products/clinicpro", "label": "ClinicPro", "sitemap_priority": "0.85", "sitemap_changefreq": "weekly"},
    {"path": "/products/menubip", "label": "MenuBip", "sitemap_priority": "0.85", "sitemap_changefreq": "weekly"},
    {"path": "/products/hotelpro", "label": "HotelPro", "sitemap_priority": "0.65", "sitemap_changefreq": "monthly"},
    {"path": "/products/hrms", "label": "HRMS", "sitemap_priority": "0.65", "sitemap_changefreq": "monthly"},
    {"path": "/products/crm", "label": "CRM", "sitemap_priority": "0.65", "sitemap_changefreq": "monthly"},
    {"path": "/products/leadstack", "label": "LeadStack", "sitemap_priority": "0.65", "sitemap_changefreq": "monthly"},
    {"path": "/work", "label": "Work", "sitemap_priority": "0.8", "sitemap_changefreq": "weekly"},
    {"path": "/blog", "label": "Blog", "sitemap_priority": "0.8", "sitemap_changefreq": "daily"},
    {"path": "/contact", "label": "Contact", "sitemap_priority": "0.6", "sitemap_changefreq": "monthly"},
]

CLINICPRO_LEGACY_PATHS = [
    "/price",
    "/features",
    "/security",
    "/integrations",
    "/apps-and-tools",
    "/practice-types",
    "/multi-clinic",
    "/professions",
    "/my-product",
]

ENTITY_SEO_COLUMNS = {
    "blogs": [
        ("robots", "VARCHAR(50) NULL"),
    ],
    "professions": [
        ("robots", "VARCHAR(50) NULL"),
        ("schema_json", "JSON NULL"),
    ],
    "integrations": [
        ("robots", "VARCHAR(50) NULL"),
        ("schema_json", "JSON NULL"),
    ],
    "product_pages": [
        ("robots", "VARCHAR(50) NULL"),
        ("schema_json", "JSON NULL"),
    ],
    "seo_site_settings": [
        ("gtm_enabled", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("gtm_container_id", "VARCHAR(50) NULL"),
        ("ga4_enabled", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("ga4_measurement_id", "VARCHAR(50) NULL"),
        ("meta_pixel_enabled", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("meta_pixel_id", "VARCHAR(50) NULL"),
        ("linkedin_enabled", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("linkedin_partner_id", "VARCHAR(50) NULL"),
        ("clarity_enabled", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("clarity_project_id", "VARCHAR(50) NULL"),
        ("custom_head_scripts", "TEXT NULL"),
        ("custom_body_scripts", "TEXT NULL"),
    ],
}


def _table_exists(connection, table_name: str) -> bool:
    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return bool(result.scalar())


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(result.scalar())


def migrate_entity_seo_columns() -> None:
    with engine.begin() as connection:
        for table_name, columns in ENTITY_SEO_COLUMNS.items():
            if not _table_exists(connection, table_name):
                continue
            for column_name, column_type in columns:
                if _column_exists(connection, table_name, column_name):
                    continue
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                )


def _remove_legacy_seo_pages(db: Session) -> None:
    if not CLINICPRO_LEGACY_PATHS:
        return
    db.query(SeoPage).filter(SeoPage.path.in_(CLINICPRO_LEGACY_PATHS)).delete(
        synchronize_session=False
    )


def cleanup_legacy_seo(db: Session) -> None:
    """Remove ClinicPro static SEO pages and ensure OCMONO defaults exist."""
    _remove_legacy_seo_pages(db)

    existing_paths = {row.path for row in db.query(SeoPage.path).all()}
    for page in OCMONO_DEFAULT_PAGES:
        if page["path"] in existing_paths:
            continue
        db.add(
            SeoPage(
                path=page["path"],
                label=page["label"],
                sitemap_include=True,
                sitemap_priority=page["sitemap_priority"],
                sitemap_changefreq=page["sitemap_changefreq"],
            )
        )

    db.commit()


def seed_seo_defaults(db: Session) -> None:
    settings = db.query(SeoSiteSettings).first()
    if not settings:
        db.add(
            SeoSiteSettings(
                site_name="OCMONO",
                title_suffix="OCMONO",
                default_meta_description=(
                    "OCMONO is a design-led digital marketing agency helping brands grow with "
                    "branding, web development, SEO, and performance marketing."
                ),
                default_og_image="/assets/img/ocmono-home/ocmono_new_logo.png",
                twitter_handle="@theocmono",
                robots_default="index,follow",
                organization_schema={
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": "OCMONO",
                    "url": "https://ocmono.com",
                    "logo": "https://ocmono.com/assets/img/ocmono-home/ocmono_new_logo.png",
                },
                sitemap_enabled=True,
                robots_extra="Disallow: /admin\nDisallow: /api",
            )
        )

    cleanup_legacy_seo(db)
