from sqlalchemy.orm import Session

from app.models.agency_page import AgencyPage

DEFAULT_PAGES = [
    {
        "page_type": "service",
        "title": "Performance Marketing",
        "slug": "performance-marketing",
        "excerpt": "Paid media and conversion systems that turn spend into pipeline.",
        "content": "<p>Meta, Google, and retargeting campaigns engineered for CPA, ROAS, and qualified leads — with creative testing and landing-page alignment baked in.</p><ul><li>Paid social &amp; search</li><li>Conversion tracking &amp; attribution</li><li>Creative testing loops</li><li>Lead quality feedback</li></ul>",
        "cover_image": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&h=800&fit=crop",
        "tags": ["Meta Ads", "Google Ads", "ROAS", "Lead gen"],
        "sort_order": 1,
        "status": "published",
    },
    {
        "page_type": "service",
        "title": "SEO & Local",
        "slug": "seo-local",
        "excerpt": "Organic and Google Business Profile growth for clinics, F&B, and local brands.",
        "content": "<p>Technical SEO, content clusters, and GBP optimization so the right customers find you — then trust you enough to enquire.</p><ul><li>Technical &amp; on-page SEO</li><li>Google Business Profile</li><li>Review &amp; reputation workflows</li><li>Local landing pages</li></ul>",
        "cover_image": "https://images.unsplash.com/photo-1432888498266-38ffec52ef0e?w=1200&h=800&fit=crop",
        "tags": ["SEO", "GBP", "Local", "Content"],
        "sort_order": 2,
        "status": "published",
    },
    {
        "page_type": "service",
        "title": "Conversion Creative",
        "slug": "conversion-creative",
        "excerpt": "Ads, landing pages, and offer creative built to convert — not just look sharp.",
        "content": "<p>Messaging, visuals, and page layouts tested against real click-to-lead outcomes for performance campaigns.</p><ul><li>Ad creative systems</li><li>Landing page UX</li><li>Offer &amp; messaging tests</li><li>Brand-safe performance design</li></ul>",
        "cover_image": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&h=800&fit=crop",
        "tags": ["Creative", "Landing pages", "CRO"],
        "sort_order": 3,
        "status": "published",
    },
    {
        "page_type": "service",
        "title": "Web & Funnels",
        "slug": "web-funnels",
        "excerpt": "Fast sites and funnels that support ads, SEO, and SaaS onboarding.",
        "content": "<p>Marketing sites, product landings, and lead funnels on modern stacks — speed, tracking, and conversion first.</p><ul><li>Marketing websites</li><li>Product landing pages</li><li>Lead capture funnels</li><li>Analytics &amp; event setup</li></ul>",
        "cover_image": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&h=800&fit=crop",
        "tags": ["Next.js", "Funnels", "CRO", "Analytics"],
        "sort_order": 4,
        "status": "published",
    },
    {
        "page_type": "service",
        "title": "Brand Strategy",
        "slug": "brand-strategy",
        "excerpt": "Positioning and identity that support growth — without slowing campaigns.",
        "content": "<p>Clear positioning, visual systems, and messaging so performance creative stays on-brand while it converts.</p>",
        "cover_image": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=1200&h=800&fit=crop",
        "tags": ["Positioning", "Visual identity", "Messaging"],
        "sort_order": 5,
        "status": "published",
    },
    {
        "page_type": "project",
        "title": "Clinic lead gen system",
        "slug": "clinic-lead-gen-system",
        "excerpt": "Paid + local SEO pipeline that booked qualified patient enquiries for a multi-location clinic.",
        "content": "<p>Campaign structure, GBP optimization, and conversion pages aligned to ClinicPro-ready intake.</p>",
        "cover_image": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1200&h=800&fit=crop",
        "tags": ["Healthcare", "Performance", "Local SEO"],
        "sort_order": 1,
        "status": "published",
    },
    {
        "page_type": "project",
        "title": "Restaurant QR growth",
        "slug": "restaurant-qr-growth",
        "excerpt": "MenuBip rollout plus paid social that lifted dine-in and takeaway orders.",
        "content": "<p>Product onboarding, QR creative, and Meta campaigns for a busy F&amp;B brand.</p>",
        "cover_image": "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=1200&h=800&fit=crop",
        "tags": ["F&B", "SaaS", "Paid social"],
        "sort_order": 2,
        "status": "published",
    },
    {
        "page_type": "project",
        "title": "SaaS product launch",
        "slug": "saas-product-launch",
        "excerpt": "Landing pages, positioning, and paid acquisition for a B2B SaaS launch.",
        "content": "<p>Go-to-market support including funnels, ads, and analytics instrumentation.</p>",
        "cover_image": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=1200&h=800&fit=crop",
        "tags": ["SaaS", "Paid media", "Funnels"],
        "sort_order": 3,
        "status": "published",
    },
]


def seed_agency_pages(db: Session):
    for item in DEFAULT_PAGES:
        existing = db.query(AgencyPage).filter(AgencyPage.slug == item["slug"]).first()
        if existing:
            for key, value in item.items():
                if key == "slug":
                    continue
                setattr(existing, key, value)
            continue
        db.add(AgencyPage(**item))
    db.commit()
