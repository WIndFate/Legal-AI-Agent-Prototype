import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from redis.asyncio import Redis

from backend.config import get_settings

logger = logging.getLogger(__name__)
INTERNAL_SERVICE_HOSTS = {"backend", "frontend", "postgres", "redis"}
WEBHOOK_MAX_FUTURE_SKEW = timedelta(minutes=5)
WEBHOOK_REPLAY_TTL_SECONDS = 24 * 60 * 60


def is_dev_payment_mode() -> bool:
    """Allow checkout bypass only in development when KOMOJU is not configured."""
    settings = get_settings()
    return settings.is_development and not settings.KOMOJU_SECRET_KEY


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

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://komoju.com/api/v1/sessions",
            auth=(settings.KOMOJU_SECRET_KEY, ""),
            json={
                "amount": amount_jpy,
                "currency": "JPY",
                "return_url": f"{frontend_base_url}/review/{order_id}",
                "default_locale": "ja",
                "email": email,
                "metadata": {"order_id": order_id},
            },
        )
        if response.is_error:
            logger.error(
                "KOMOJU session creation failed: status=%s body=%s order_id=%s amount_jpy=%s frontend_base_url=%s",
                response.status_code,
                response.text,
                order_id,
                amount_jpy,
                frontend_base_url,
            )
        response.raise_for_status()
        data = response.json()
        return data["session_url"]


async def verify_webhook(payload: bytes, signature: str) -> tuple[dict | None, str | None]:
    """Verify KOMOJU webhook signature and return parsed event plus rejection reason."""
    settings = get_settings()

    if settings.is_development and not settings.KOMOJU_WEBHOOK_SECRET:
        # Local development accepts unsigned webhook payloads.
        try:
            return _validate_webhook_event(json.loads(payload)), None
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            reason = str(exc) if str(exc) else "invalid_payload"
            logger.warning("Invalid KOMOJU webhook payload in development: %s", reason)
            return None, reason

    expected = hmac.HMAC(
        settings.KOMOJU_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        logger.warning("Invalid KOMOJU webhook signature")
        return None, "invalid_signature"

    try:
        return _validate_webhook_event(json.loads(payload)), None
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        reason = str(exc) if str(exc) else "invalid_payload"
        logger.warning("Invalid KOMOJU webhook payload: %s", reason)
        return None, reason


def _validate_webhook_event(event: dict) -> dict:
    """Validate minimal webhook metadata required for replay protection."""
    if not isinstance(event, dict):
        raise ValueError("event_payload_not_object")

    event_id = str(event.get("id") or "").strip()
    if not event_id:
        raise ValueError("event_id_missing")

    created_at_raw = str(event.get("created_at") or "").strip()
    if not created_at_raw:
        raise ValueError("event_created_at_missing")

    created_at = _parse_iso8601_timestamp(created_at_raw)
    if created_at is None:
        raise ValueError("event_created_at_invalid")

    now = datetime.now(timezone.utc)
    if created_at - now > WEBHOOK_MAX_FUTURE_SKEW:
        raise ValueError("event_created_at_in_future")

    return event


def _parse_iso8601_timestamp(value: str) -> datetime | None:
    """Parse an ISO 8601 timestamp into an aware UTC datetime."""
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _webhook_replay_key(event_id: str) -> str:
    return f"payment_webhook:seen:{event_id}"


async def record_webhook_event(redis: Redis, event_id: str) -> bool:
    """Mark a webhook event as seen. Returns False when the event is a replay."""
    if not event_id:
        raise ValueError("event_id_missing")
    return bool(
        await redis.set(
            _webhook_replay_key(event_id),
            "1",
            ex=WEBHOOK_REPLAY_TTL_SECONDS,
            nx=True,
        )
    )
