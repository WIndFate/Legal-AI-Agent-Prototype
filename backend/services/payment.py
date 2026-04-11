import hashlib
import hmac
import json
import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)
INTERNAL_SERVICE_HOSTS = {"backend", "frontend", "postgres", "redis"}
DEFAULT_KOMOJU_PAYMENT_METHODS = {
    "session_payment_types": [
        "credit_card",
        "unionpay",
        "alipay",
        "wechatpay",
        "paypay",
        "credit_card_korea",
        "credit_card_brazil",
        "kakaopay",
        "dana",
        "gcash",
        "tng",
        "alipay_hk",
        "jkopay",
    ]
}


def is_dev_payment_mode() -> bool:
    """Allow checkout bypass only in development when KOMOJU is not configured."""
    settings = get_settings()
    return settings.is_development and not settings.KOMOJU_SECRET_KEY


@lru_cache(maxsize=1)
def get_komoju_payment_methods() -> dict[str, object]:
    settings = get_settings()
    config_path = Path(settings.KOMOJU_PAYMENT_METHODS_FILE)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if _payment_methods_config_is_valid(payload):
            return payload
        logger.warning(
            "Invalid KOMOJU payment-method configuration in %s; falling back to defaults",
            config_path,
        )
    except (OSError, json.JSONDecodeError):
        logger.warning(
            "Failed to load KOMOJU payment-method configuration from %s; falling back to defaults",
            config_path,
        )

    return DEFAULT_KOMOJU_PAYMENT_METHODS


def get_komoju_session_payment_types() -> list[str]:
    payload = get_komoju_payment_methods()
    session_payment_types = payload.get("session_payment_types", [])
    return [str(value) for value in session_payment_types]


def resolve_frontend_base_url(
    *,
    origin_header: str | None = None,
    referer_header: str | None = None,
    forwarded_proto: str | None = None,
    forwarded_host: str | None = None,
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

    def is_internal_host(raw: str | None) -> bool:
        if not raw:
            return True
        host = raw.strip().lower()
        if not host:
            return True
        if host in {"localhost", "127.0.0.1"}:
            return False
        if host in INTERNAL_SERVICE_HOSTS:
            return True
        if "." in host or ":" in host:
            return False
        return True

    for raw_origin in (origin_header, referer_header):
        request_origin = normalize_origin(raw_origin)
        if request_origin:
            request_host = urlparse(request_origin).hostname or ""
            if not is_internal_host(request_host):
                return request_origin

    frontend_origin = normalize_origin(settings.FRONTEND_URL)
    if frontend_origin and not settings.uses_local_frontend_url():
        return frontend_origin

    header_host = forwarded_host or host_header
    if header_host:
        scheme = (forwarded_proto or "http").split(",")[0].strip() or "http"
        host = header_host.split(",")[0].strip()
        hostname = host.split(":")[0].strip()
        if host and not is_internal_host(hostname):
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

    payment_types = get_komoju_session_payment_types()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://komoju.com/api/v1/sessions",
            auth=(settings.KOMOJU_SECRET_KEY, ""),
            json={
                "amount": amount_jpy,
                "currency": "JPY",
                "payment_types": payment_types,
                "return_url": f"{frontend_base_url}/review/{order_id}",
                "default_locale": "ja",
                "email": email,
                "metadata": {"order_id": order_id},
            },
        )
        if response.is_error:
            logger.error(
                "KOMOJU session creation failed: status=%s body=%s order_id=%s amount_jpy=%s frontend_base_url=%s payment_types=%s",
                response.status_code,
                response.text,
                order_id,
                amount_jpy,
                frontend_base_url,
                payment_types,
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


def _payment_methods_config_is_valid(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False

    session_payment_types = payload.get("session_payment_types")
    if not isinstance(session_payment_types, list) or not session_payment_types:
        return False

    return all(isinstance(value, str) and value.strip() for value in session_payment_types)
