from decimal import Decimal

CHECKOUT_ADDONS = [
    {
        "slug": "pharmacy",
        "icon": "pharmacy",
        "title": "In-clinic Pharmacy",
        "description": "Set up and manage your own in-clinic pharmacy with integrated inventory and billing workflows.",
        "price_label": "STARTING AT",
        "amount": Decimal("7699.00"),
        "billing_label": "/yr",
    },
    {
        "slug": "credits",
        "icon": "credits",
        "title": "Clinic Credits",
        "description": "Stay in touch with your patients by sending messages using prepaid Clinic credits.",
        "price_label": "STARTING AT",
        "amount": Decimal("350.00"),
        "billing_label": "",
    },
    {
        "slug": "website",
        "icon": "website",
        "title": "Personalised Website",
        "description": "Boost your online presence with a personalized website for your patients and discovery.",
        "price_label": "STARTING AT",
        "amount": Decimal("13999.00"),
        "billing_label": "",
    },
    {
        "slug": "communication",
        "icon": "communication",
        "title": "Own Your Communication",
        "description": "Send messages via WhatsApp & SMS from your business account today.",
        "price_label": "STARTING AT",
        "amount": Decimal("24499.00"),
        "billing_label": "/yr",
    },
]

_ADDON_BY_SLUG = {item["slug"]: item for item in CHECKOUT_ADDONS}


def list_checkout_addons() -> list[dict]:
    return [
        {
            "slug": item["slug"],
            "icon": item["icon"],
            "title": item["title"],
            "description": item["description"],
            "price_label": item["price_label"],
            "amount": item["amount"],
            "billing_label": item["billing_label"],
        }
        for item in CHECKOUT_ADDONS
    ]


def resolve_checkout_addons(addon_slugs: list[str] | None) -> tuple[list[dict], Decimal]:
    if not addon_slugs:
        return [], Decimal("0.00")

    selected = []
    seen = set()
    total = Decimal("0.00")
    for slug in addon_slugs:
        key = (slug or "").strip().lower()
        if not key or key in seen:
            continue
        addon = _ADDON_BY_SLUG.get(key)
        if not addon:
            raise ValueError(f"Unknown add-on: {slug}")
        seen.add(key)
        selected.append(
            {
                "slug": addon["slug"],
                "title": addon["title"],
                "amount": addon["amount"],
                "billing_label": addon["billing_label"],
            }
        )
        total += addon["amount"]

    return selected, total.quantize(Decimal("0.01"))
