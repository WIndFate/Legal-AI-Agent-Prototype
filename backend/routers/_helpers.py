import hmac
import secrets
from uuid import UUID

from fastapi import Header, HTTPException

from backend.config import get_settings


def parse_order_id(order_id: str) -> UUID:
    # Invalid UUID strings map to 404 so mistyped order IDs behave like
    # "order does not exist" instead of surfacing an asyncpg DataError as 500.
    try:
        return UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Order not found")


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = settings.ADMIN_API_TOKEN
    if not expected or not x_admin_token:
        raise HTTPException(status_code=404, detail="Not found")
    if not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=404, detail="Not found")


def build_order_access_token() -> str:
    return secrets.token_urlsafe(32)


def build_order_share_token() -> str:
    return secrets.token_urlsafe(32)


def require_order_token(
    *,
    provided_token: str | None,
    access_token: str | None,
    share_token: str | None = None,
    allow_share_token: bool = False,
) -> None:
    if not provided_token or not access_token:
        raise HTTPException(status_code=404, detail="Not found")
    if hmac.compare_digest(provided_token, access_token):
        return
    if allow_share_token and share_token and hmac.compare_digest(provided_token, share_token):
        return
    raise HTTPException(status_code=404, detail="Not found")
