from __future__ import annotations

import hashlib
import json
import logging
from uuid import uuid4

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.config import get_settings

logger = logging.getLogger(__name__)

QUOTE_CACHE_VERSION = "v1"


def extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def build_contract_content_hash(contract_text: str) -> str:
    normalized = "\n".join(line.strip() for line in contract_text.strip().splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_quote_token() -> str:
    return uuid4().hex


async def enforce_upload_rate_limit(redis: Redis | None, client_ip: str) -> None:
    settings = get_settings()
    limited = await _consume_rate_limit(
        redis,
        key=f"upload-rate:{client_ip}",
        limit=settings.UPLOAD_RATE_LIMIT_COUNT,
        window_seconds=settings.UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    )
    if limited:
        raise HTTPException(status_code=429, detail="Too many upload requests. Please try again later.")


async def allow_preview_generation(redis: Redis | None, client_ip: str) -> bool:
    settings = get_settings()
    limited = await _consume_rate_limit(
        redis,
        key=f"preview-rate:{client_ip}",
        limit=settings.PREVIEW_RATE_LIMIT_COUNT,
        window_seconds=settings.PREVIEW_RATE_LIMIT_WINDOW_SECONDS,
    )
    return not limited


async def load_cached_quote(redis: Redis | None, content_hash: str) -> dict | None:
    if redis is None:
        return None
    try:
        payload = await redis.get(_content_cache_key(content_hash))
    except RedisError as exc:
        logger.warning("Quote content cache lookup failed: %s", exc)
        return None
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def store_cached_quote(
    redis: Redis | None,
    *,
    content_hash: str,
    quote_token: str,
    payload: dict,
    upload_token: str | None = None,
) -> None:
    if redis is None:
        return
    ttl = get_settings().QUOTE_CACHE_TTL_SECONDS
    encoded = json.dumps(payload, ensure_ascii=False)
    try:
        await redis.set(_content_cache_key(content_hash), encoded, ex=ttl)
        await redis.set(_token_cache_key(quote_token), encoded, ex=ttl)
        if upload_token:
            await redis.set(_upload_cache_key(upload_token), encoded, ex=ttl)
    except RedisError as exc:
        logger.warning("Quote cache store failed: %s", exc)


async def load_quote_context(redis: Redis | None, quote_token: str | None) -> dict | None:
    if redis is None or not quote_token:
        return None
    try:
        payload = await redis.get(_token_cache_key(quote_token))
    except RedisError as exc:
        logger.warning("Quote token cache lookup failed: %s", exc)
        return None
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def load_upload_quote_context(redis: Redis | None, upload_token: str | None) -> dict | None:
    if redis is None or not upload_token:
        return None
    try:
        payload = await redis.get(_upload_cache_key(upload_token))
    except RedisError as exc:
        logger.warning("Upload quote cache lookup failed: %s", exc)
        return None
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def _consume_rate_limit(redis: Redis | None, *, key: str, limit: int, window_seconds: int) -> bool:
    if redis is None:
        return False
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        return int(current) > limit
    except RedisError as exc:
        logger.warning("Rate limit check failed for %s: %s", key, exc)
        return False


def _content_cache_key(content_hash: str) -> str:
    return f"quote-cache:{QUOTE_CACHE_VERSION}:content:{content_hash}"


def _token_cache_key(quote_token: str) -> str:
    return f"quote-cache:{QUOTE_CACHE_VERSION}:token:{quote_token}"


def _upload_cache_key(upload_token: str) -> str:
    return f"quote-cache:{QUOTE_CACHE_VERSION}:upload:{upload_token}"
