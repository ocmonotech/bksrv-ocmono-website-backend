import os
from typing import Any

import requests


OCMONO_SYSTEM_PROMPT = """
You are OCMONO's website assistant — a design-led digital marketing agency.

Help visitors with services, pricing, portfolio/work, process, and how to get in touch.

Product facts you can use:
- Services: brand strategy, web development, SEO, digital marketing, e-commerce, UI/UX design.
- Pricing retainers: Part-time from $2,450/mo, Full-time from $3,950/mo (popular), Your own team from $5,450/mo. Pause or cancel anytime.
- Process: Idea → Research → Web Design → Development → Launch → Support.
- Contact: contact@ocmono.com, +91 8850 533614, contact page, or message via chatbot.
- Visitors can explore services, view pricing, browse work, or send a project inquiry.

Rules:
- Be concise, friendly, and practical (2–5 short sentences unless asked for detail).
- Do not invent features, prices, or guarantees.
- If unsure, suggest contacting the OCMONO team or using the contact form.
- Do not mention ClinicPro or clinic software.
- Do not mention that you are an AI model unless asked.
""".strip()


def openai_enabled() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def _openai_model() -> str:
    return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()


def _default_options() -> list[dict[str, Any]]:
    return [
        {"id": "contact", "label": "Contact us", "action": "contact"},
        {"id": "pricing", "label": "Pricing & plans", "action": "pricing"},
        {"id": "services", "label": "Our services", "action": "services"},
        {"id": "back-main", "label": "Main menu", "action": "main"},
    ]


def _infer_options(reply: str) -> list[dict[str, Any]]:
    lower = (reply or "").lower()
    options: list[dict[str, Any]] = []

    if any(word in lower for word in ("contact", "support", "whatsapp", "call", "message", "inquiry", "reach")):
        options.append({"id": "contact", "label": "Contact us", "action": "contact"})
    if any(word in lower for word in ("price", "pricing", "plan", "$", "budget", "retainer")):
        options.append({"id": "pricing", "label": "View pricing", "action": "pricing"})
    if any(word in lower for word in ("service", "branding", "seo", "marketing", "website", "design")):
        options.append({"id": "services", "label": "Our services", "action": "services"})
    if any(word in lower for word in ("work", "portfolio", "project", "case study")):
        options.append(
            {"id": "nav-work", "label": "Our work", "action": "navigate", "href": "/work"}
        )

    if not options:
        return _default_options()

    options.append({"id": "back-main", "label": "Main menu", "action": "main"})
    seen = set()
    unique = []
    for item in options:
        key = item.get("id")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:5]


def ask_openai(*, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Call OpenAI Chat Completions. Returns {reply, options, source}."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    messages: list[dict[str, str]] = [{"role": "system", "content": OCMONO_SYSTEM_PROMPT}]

    for item in (history or [])[-8:]:
        role = item.get("role")
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text[:2000]})
        elif role in {"bot", "assistant"}:
            messages.append({"role": "assistant", "content": text[:2000]})

    messages.append({"role": "user", "content": message.strip()[:2000]})

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _openai_model(),
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 450,
        },
        timeout=45,
    )

    if response.status_code >= 400:
        try:
            payload = response.json()
            api_message = ((payload.get("error") or {}).get("message") or response.text)[:400]
            api_type = (payload.get("error") or {}).get("type") or ""
        except Exception:
            api_message = response.text[:400]
            api_type = ""

        if response.status_code == 429 or "insufficient_quota" in api_type or "quota" in api_message.lower():
            raise RuntimeError(
                "OpenAI quota exceeded (429). Add billing/credits at https://platform.openai.com/account/billing"
            )
        if response.status_code == 401:
            raise RuntimeError("OpenAI API key is invalid (401). Check OPENAI_API_KEY.")
        raise RuntimeError(f"OpenAI error ({response.status_code}): {api_message}")

    data = response.json()
    reply = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip()

    if not reply:
        raise RuntimeError("OpenAI returned an empty reply")

    return {
        "reply": reply,
        "options": _infer_options(reply),
        "source": "openai",
        "model": _openai_model(),
    }
