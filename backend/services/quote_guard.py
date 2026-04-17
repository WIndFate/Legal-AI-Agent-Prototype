from __future__ import annotations

import hashlib
import json
import logging
from uuid import uuid4

OCR_CACHE_VERSION = "v1"

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.config import get_settings

logger = logging.getLogger(__name__)

QUOTE_CACHE_VERSION = "v1"


def extract_client_ip(request: Request) -> str:
    """Return the client IP, preferring proxy-authoritative headers.

    Order of trust:
      1. `Fly-Client-IP` — set by Fly.io edge and not client-settable upstream.
      2. Rightmost entry of `X-Forwarded-For` — this is the IP inserted by the
         closest trusted proxy. The leftmost entry is client-controlled and was
         historically used here, which let an attacker spoof any source IP
         and bypass the per-IP OCR abuse counter by adding their own header.
      3. `request.client.host` — direct socket peer.

    Dev note: behind the Vite dev proxy the rightmost XFF entry resolves to
    the container bridge IP, so all local developers share one abuse counter.
    This is expected and does not affect production, which is fronted by Fly.
    """
    fly_client = request.headers.get("fly-client-ip", "").strip()
    if fly_client:
        return fly_client
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def build_contract_content_hash(contract_text: str) -> str:
    normalized = "\n".join(line.strip() for line in contract_text.strip().splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_file_hash(data: bytes) -> str:
    """SHA-256 of raw file bytes. Used to detect repeated uploads before OCR."""
    return hashlib.sha256(data).hexdigest()


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
        raise HTTPException(status_code=429, detail="upload_rate_limited")


async def allow_preview_generation(redis: Redis | None, client_ip: str) -> bool:
    """Return True if clause preview (pre-payment LLM call) may run.

    Fail-closed: Redis unavailable or errors out -> deny preview, since the
    preview path calls a pre-payment LLM that could be abused if unbounded.
    """
    settings = get_settings()
    limited = await _consume_rate_limit(
        redis,
        key=f"preview-rate:{client_ip}",
        limit=settings.PREVIEW_RATE_LIMIT_COUNT,
        window_seconds=settings.PREVIEW_RATE_LIMIT_WINDOW_SECONDS,
        fail_closed=True,
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
) -> None:
    if redis is None:
        return
    ttl = get_settings().QUOTE_CACHE_TTL_SECONDS
    encoded = json.dumps(payload, ensure_ascii=False)
    try:
        await redis.set(_content_cache_key(content_hash), encoded, ex=ttl)
        await redis.set(_token_cache_key(quote_token), encoded, ex=ttl)
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


async def _consume_rate_limit(
    redis: Redis | None,
    *,
    key: str,
    limit: int,
    window_seconds: int,
    fail_closed: bool = False,
) -> bool:
    """Increment a per-IP counter and return True when over limit.

    - `fail_closed=False` (default, for generic upload rate limit): treat Redis
      outages as "not limited" so a broken cache doesn't break the service.
    - `fail_closed=True` (for LLM/OCR pre-payment paths): treat Redis outages
      as "over limit" so untracked cost cannot accumulate.
    """
    if redis is None:
        return True if fail_closed else False
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        return int(current) > limit
    except RedisError as exc:
        logger.warning("Rate limit check failed for %s: %s (fail_closed=%s)", key, exc, fail_closed)
        return True if fail_closed else False


async def load_ocr_result_cache(redis: Redis | None, file_hash: str) -> dict | None:
    """Return cached OCR result for raw file bytes (keyed by file hash), or None."""
    if redis is None:
        return None
    try:
        payload = await redis.get(f"ocr-cache:{OCR_CACHE_VERSION}:{file_hash}")
    except RedisError as exc:
        logger.warning("OCR result cache lookup failed: %s", exc)
        return None
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def store_ocr_result_cache(
    redis: Redis | None,
    file_hash: str,
    contract_text: str,
    ocr_snapshot: dict | None,
) -> None:
    """Cache OCR result keyed by raw file hash. Same TTL as quote cache."""
    if redis is None:
        return
    ttl = get_settings().QUOTE_CACHE_TTL_SECONDS
    payload = json.dumps({"text": contract_text, "snapshot": ocr_snapshot}, ensure_ascii=False)
    try:
        await redis.set(f"ocr-cache:{OCR_CACHE_VERSION}:{file_hash}", payload, ex=ttl)
    except RedisError as exc:
        logger.warning("OCR result cache store failed: %s", exc)


def _content_cache_key(content_hash: str) -> str:
    return f"quote-cache:{QUOTE_CACHE_VERSION}:content:{content_hash}"


def _token_cache_key(quote_token: str) -> str:
    return f"quote-cache:{QUOTE_CACHE_VERSION}:token:{quote_token}"
