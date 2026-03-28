import hashlib
import hmac
import json
import logging
from urllib.parse import urlparse

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


def is_dev_payment_mode() -> bool:
    """Allow checkout bypass only in development when KOMOJU is not configured."""
    settings = get_settings()
    return settings.is_development and not settings.KOMOJU_SECRET_KEY


def resolve_frontend_base_url(
    *,
    origin_header: str | None = None,
    forwarded_proto: str | None = None,
    host_header: str | None = None,
) -> str:
    """Prefer the active browser origin in development/LAN scenarios over localhost defaults."""
    settings = get_settings()

    def normalize_origin(raw: str | None) -> str | None:
        if not raw:
            return None
        value = raw.strip().rstrip("/")
        if not value:
            return None
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return None

    request_origin = normalize_origin(origin_header)
    if request_origin:
        request_host = urlparse(request_origin).hostname or ""
        if request_host not in {"localhost", "127.0.0.1"}:
            return request_origin

    frontend_origin = normalize_origin(settings.FRONTEND_URL)
    if frontend_origin and not settings.uses_local_frontend_url():
        return frontend_origin

    if host_header:
        scheme = (forwarded_proto or "http").split(",")[0].strip() or "http"
        host = host_header.split(",")[0].strip()
        if host:
            resolved = normalize_origin(f"{scheme}://{host}")
            if resolved:
                return resolved

    return frontend_origin or "http://localhost:5173"


async def create_payment_session(order_id: str, amount_jpy: int, email: str, frontend_base_url: str) -> str:
    """Create a KOMOJU payment session and return the session URL."""
    settings = get_settings()

    if is_dev_payment_mode():
        # Local development skips the external checkout page.
        logger.warning("KOMOJU_SECRET_KEY not set, returning placeholder payment URL")
        return f"{frontend_base_url}/review/{order_id}?dev_payment=true"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://komoju.com/api/v1/sessions",
            auth=(settings.KOMOJU_SECRET_KEY, ""),
            json={
                "amount": amount_jpy,
                "currency": "JPY",
                "payment_types": ["credit_card", "wechat_pay", "alipay"],
                "return_url": f"{frontend_base_url}/review/{order_id}",
                "default_locale": "ja",
                "email": email,
                "metadata": {"order_id": order_id},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["session_url"]


async def verify_webhook(payload: bytes, signature: str) -> dict | None:
    """Verify KOMOJU webhook signature and return parsed event."""
    settings = get_settings()

    if settings.is_development and not settings.KOMOJU_WEBHOOK_SECRET:
        # Local development accepts unsigned webhook payloads.
        return json.loads(payload)

    expected = hmac.HMAC(
        settings.KOMOJU_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        logger.warning("Invalid KOMOJU webhook signature")
        return None

    return json.loads(payload)
