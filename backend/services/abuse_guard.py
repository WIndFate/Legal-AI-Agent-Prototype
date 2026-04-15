"""Abuse guard: tracks unpaid OCR consumption per IP to limit pre-payment cost waste.

Logic:
  waste = uploads_count - paid_count
  If waste >= OCR_WASTE_DAILY_LIMIT, the next OCR call is rejected.

This means a user who always pays is never blocked.
A user who uploads 3 different files without paying is blocked on the 4th attempt.
Any subsequent payment reduces the effective waste count.

All operations are fail-closed on Redis errors so that OCR is never untracked.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Redis errors that should trigger fail-closed behavior on high-cost paths.
# asyncio.TimeoutError is NOT a subclass of RedisError, so it must be listed explicitly.
_REDIS_FAILURE_EXCEPTIONS = (RedisError, asyncio.TimeoutError, ConnectionError)

# Atomic safe-decrement: only decrement when the current value is > 0.
# Protects against a race where the uploads key expired between INCR and DECR
# (rollback) — a bare DECR would create the key at -1 with no TTL, permanently
# granting an extra free OCR slot for that IP.
_SAFE_DECR_SCRIPT = """
local v = redis.call('GET', KEYS[1])
if v and tonumber(v) > 0 then
  return redis.call('DECR', KEYS[1])
end
return 0
"""


def _uploads_key(ip: str) -> str:
    return f"abuse:uploads:{ip}"


def _paid_key(ip: str) -> str:
    return f"abuse:paid:{ip}"


async def check_ocr_allowed(redis: Redis | None, ip: str) -> bool:
    """Return False if this IP has exceeded the OCR waste limit.

    Fail-closed: if Redis is unavailable or raises any transient error,
    OCR is blocked to prevent untracked cost.
    """
    settings = get_settings()
    if redis is None:
        logger.warning("abuse_guard redis unavailable, fail-closed ip=%s", ip)
        return False
    try:
        uploads = int(await redis.get(_uploads_key(ip)) or 0)
        paid = int(await redis.get(_paid_key(ip)) or 0)
        waste = uploads - paid
        return waste < settings.OCR_WASTE_DAILY_LIMIT
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.warning("abuse_guard check_ocr_allowed redis error ip=%s: %s", ip, exc)
        return False  # fail-closed


async def record_ocr_upload(redis: Redis | None, ip: str) -> None:
    """Increment upload counter for this IP. Call before triggering Vision OCR.

    Fail-closed: if Redis is unavailable or errors out, raises HTTPException(503)
    so OCR is never triggered without a successful counter increment. This closes
    the TOCTOU window where check_ocr_allowed could pass but record could silently
    lose the increment, allowing unlimited untracked OCR until Redis recovers.
    """
    if redis is None:
        logger.error("abuse_guard record_ocr_upload redis unavailable, fail-closed ip=%s", ip)
        raise HTTPException(status_code=503, detail="service_unavailable")
    settings = get_settings()
    try:
        current = await redis.incr(_uploads_key(ip))
        if current == 1:
            await redis.expire(_uploads_key(ip), settings.OCR_WASTE_WINDOW_SECONDS)
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.error("abuse_guard record_ocr_upload redis error ip=%s: %s", ip, exc)
        raise HTTPException(status_code=503, detail="service_unavailable") from exc


async def rollback_ocr_upload(redis: Redis | None, ip: str) -> None:
    """Decrement upload counter. Call when OCR fails so the slot is returned.

    Safe to fail silently: if the INCR never succeeded (Redis was down), there is
    nothing to roll back. If the INCR succeeded but DECR fails, the counter will
    naturally expire via TTL.
    """
    if redis is None:
        return
    try:
        await redis.eval(_SAFE_DECR_SCRIPT, 1, _uploads_key(ip))
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.warning("abuse_guard rollback_ocr_upload redis error ip=%s: %s", ip, exc)


async def record_payment(redis: Redis | None, ip: str | None) -> None:
    """Increment paid counter for this IP. Call when an order is confirmed as paid.

    Safe to fail silently: if the INCR is lost, the user may briefly see a lower
    upload quota, but the TTL will restore it. Never block a successful payment
    on Redis availability.
    """
    if redis is None or not ip:
        return
    settings = get_settings()
    try:
        current = await redis.incr(_paid_key(ip))
        if current == 1:
            await redis.expire(_paid_key(ip), settings.OCR_WASTE_WINDOW_SECONDS)
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.warning("abuse_guard record_payment redis error ip=%s: %s", ip, exc)
