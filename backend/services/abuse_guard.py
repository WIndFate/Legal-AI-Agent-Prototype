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

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _uploads_key(ip: str) -> str:
    return f"abuse:uploads:{ip}"


def _paid_key(ip: str) -> str:
    return f"abuse:paid:{ip}"


async def check_ocr_allowed(redis: Redis | None, ip: str) -> bool:
    """Return False if this IP has exceeded the OCR waste limit.

    Fail-closed: if Redis is unavailable, OCR is blocked to prevent untracked cost.
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
    except RedisError as exc:
        logger.warning("abuse_guard check_ocr_allowed redis error ip=%s: %s", ip, exc)
        return False  # fail-closed


async def record_ocr_upload(redis: Redis | None, ip: str) -> None:
    """Increment upload counter for this IP. Call before triggering Vision OCR."""
    if redis is None:
        return
    settings = get_settings()
    try:
        current = await redis.incr(_uploads_key(ip))
        if current == 1:
            await redis.expire(_uploads_key(ip), settings.OCR_WASTE_WINDOW_SECONDS)
    except RedisError as exc:
        logger.warning("abuse_guard record_ocr_upload redis error ip=%s: %s", ip, exc)


async def rollback_ocr_upload(redis: Redis | None, ip: str) -> None:
    """Decrement upload counter. Call when OCR fails so the slot is returned."""
    if redis is None:
        return
    try:
        await redis.decr(_uploads_key(ip))
    except RedisError as exc:
        logger.warning("abuse_guard rollback_ocr_upload redis error ip=%s: %s", ip, exc)


async def record_payment(redis: Redis | None, ip: str | None) -> None:
    """Increment paid counter for this IP. Call when an order is confirmed as paid."""
    if redis is None or not ip:
        return
    settings = get_settings()
    try:
        current = await redis.incr(_paid_key(ip))
        if current == 1:
            await redis.expire(_paid_key(ip), settings.OCR_WASTE_WINDOW_SECONDS)
    except RedisError as exc:
        logger.warning("abuse_guard record_payment redis error ip=%s: %s", ip, exc)
