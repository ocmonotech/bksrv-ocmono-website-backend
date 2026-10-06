from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
import os
from pathlib import Path
import warnings

from dotenv import load_dotenv

# Pydantic v2 warns about `schema_json` field names shadowing BaseModel helpers.
# The API intentionally keeps `schema_json` for backward-compatible payloads.
warnings.filterwarnings(
    "ignore",
    message=r'Field name "schema_json" in ".+" shadows an attribute in parent "BaseModel"',
    category=UserWarning,
)

from app.database import Base, engine
from app.routers.blogs import router as blog_router
from app.routers.blogs import upload_router
from app.routers.admin import router as admin_router
from app.routers.reviews import router as review_router
from app.routers.content import router as content_router
from app.routers.professions import router as profession_router
from app.routers.integrations import router as integration_router
from app.routers.product_pages import router as product_page_router
from app.routers.contact import router as contact_router
from app.routers.demo_bookings import router as demo_booking_router
from app.routers.admin_contact import router as admin_contact_router
from app.routers.admin_dashboard import router as admin_dashboard_router
from app.routers.seo import router as seo_router
from app.routers.chatbot import router as chatbot_router
from app.routers.admin_chatbot import router as admin_chatbot_router
from app.routers.agency_pages import router as agency_page_router
from app.routers.newsletter import router as newsletter_router
from app.services.blog_seed import migrate_blog_seo_columns, seed_blogs, sync_blogs_from_seed
from app.services.profession_seed import seed_professions
from app.services.integration_seed import seed_integrations
from app.services.product_page_seed import seed_product_pages
from app.services.agency_page_seed import seed_agency_pages
from app.services.content_seed import seed_content_blocks
from app.services.seo_migrate import cleanup_legacy_seo, migrate_entity_seo_columns, seed_seo_defaults
from app.models.review import Review  # noqa: F401
from app.models.content_block import ContentBlock  # noqa: F401
from app.models.profession import Profession  # noqa: F401
from app.models.integration import Integration  # noqa: F401
from app.models.product_page import ProductPage  # noqa: F401
from app.models.contact_submission import ContactSubmission  # noqa: F401
from app.models.email_log import EmailLog  # noqa: F401
from app.models.seo import SeoPage, SeoRedirect, SeoSiteSettings  # noqa: F401
from app.models.chatbot import ChatbotWorkflow, ChatbotSession, ChatbotMessage  # noqa: F401
from app.models.agency_page import AgencyPage  # noqa: F401
from app.models.newsletter_subscriber import NewsletterSubscriber  # noqa: F401

load_dotenv()

app = FastAPI(
    title="ClinicPro API",
    version="1.0.0",
    description=(
        "ClinicPro marketing site API. "
        "Billing, checkout, and customer accounts are handled at accounts.clinicpro.cc."
    ),
)


# Explicit origins from env (comma-separated) plus common local defaults.
_raw_origins = ",".join(
    filter(
        None,
        [
            os.getenv("FRONTEND_ORIGINS", ""),
            os.getenv("FRONTEND_ORIGIN", ""),
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )
)

allowed_origins = []
_seen = set()
for origin in _raw_origins.split(","):
    cleaned = origin.strip().rstrip("/")
    if cleaned and cleaned not in _seen:
        _seen.add(cleaned)
        allowed_origins.append(cleaned)

# Allow LAN / phone-network access during local Next.js "Network" URL testing
# (e.g. http://192.168.1.12:3000) without listing every IP.
_local_origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=_local_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_admin_users_table():
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS admin_users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(150) UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) DEFAULT 'super_admin',
        is_active TINYINT(1) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
    """

    with engine.begin() as connection:
        connection.execute(text(create_table_sql))


def migrate_product_page_categories():
    """Keep existing MySQL installations compatible with portfolio + SaaS categories."""
    if engine.dialect.name != "mysql":
        return

    statement = """
    ALTER TABLE product_pages
    MODIFY COLUMN category ENUM(
        'apps-tools',
        'practice-types',
        'multi-clinic',
        'portfolio-applications',
        'portfolio-websites',
        'saas-product'
    ) NOT NULL
    """
    with engine.begin() as connection:
        connection.execute(text(statement))


def migrate_product_page_capabilities():
    """Add structured portfolio capabilities without changing legacy page behavior."""
    columns = {column["name"] for column in inspect(engine).get_columns("product_pages")}
    if "capabilities_json" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE product_pages ADD COLUMN capabilities_json JSON NULL"))


def migrate_product_page_saas_meta():
    """Drupal-like field bundle for SaaS product content type."""
    try:
        columns = {column["name"] for column in inspect(engine).get_columns("product_pages")}
    except Exception:
        return
    if "saas_meta_json" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE product_pages ADD COLUMN saas_meta_json JSON NULL"))


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    create_admin_users_table()
    migrate_product_page_categories()
    migrate_product_page_capabilities()
    migrate_product_page_saas_meta()
    migrate_blog_seo_columns()
    migrate_entity_seo_columns()

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed_blogs(db)
        sync_blogs_from_seed(db)
        seed_professions(db)
        seed_integrations(db)
        seed_product_pages(db)
        seed_content_blocks(db)
        seed_agency_pages(db)
        seed_seo_defaults(db)
        cleanup_legacy_seo(db)
    finally:
        db.close()


uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=uploads_dir),
    name="uploads",
)

app.include_router(blog_router)
app.include_router(upload_router)
app.include_router(admin_router)
app.include_router(review_router)
app.include_router(content_router)
app.include_router(profession_router)
app.include_router(integration_router)
app.include_router(product_page_router)
app.include_router(contact_router)
app.include_router(demo_booking_router)
app.include_router(admin_contact_router)
app.include_router(admin_dashboard_router)
app.include_router(seo_router)
app.include_router(chatbot_router)
app.include_router(admin_chatbot_router)
app.include_router(newsletter_router)
app.include_router(agency_page_router)


@app.get("/health")
def health():
    return {"status": "ok"}
