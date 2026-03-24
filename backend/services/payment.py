import hashlib
import hmac
import json
import logging

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


def is_dev_payment_mode() -> bool:
    """Treat missing KOMOJU secret as local development mode."""
    return not bool(get_settings().KOMOJU_SECRET_KEY)


async def create_payment_session(order_id: str, amount_jpy: int, email: str) -> str:
    """Create a KOMOJU payment session and return the session URL."""
    settings = get_settings()

    if is_dev_payment_mode():
        # Local development skips the external checkout page.
        logger.warning("KOMOJU_SECRET_KEY not set, returning placeholder payment URL")
        return f"http://localhost:5173/review/{order_id}?dev_payment=true"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://komoju.com/api/v1/sessions",
            auth=(settings.KOMOJU_SECRET_KEY, ""),
            json={
                "amount": amount_jpy,
                "currency": "JPY",
                "payment_types": ["credit_card", "wechat_pay", "alipay"],
                "return_url": f"{settings.FRONTEND_URL}/review/{order_id}",
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

    if not settings.KOMOJU_WEBHOOK_SECRET:
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
