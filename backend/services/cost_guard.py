from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.config import get_settings
from backend.services.analytics import capture_message

logger = logging.getLogger(__name__)
_JST = ZoneInfo("Asia/Tokyo")
_REDIS_FAILURE_EXCEPTIONS = (RedisError, asyncio.TimeoutError, ConnectionError, RuntimeError)


def _daily_cost_key() -> str:
    return f"cost_guard:daily:{datetime.now(_JST).date().isoformat()}"


async def check_budget_allowed(redis: Redis | None, estimated_jpy: float) -> bool:
    """Return whether today's OCR spend may increase by the given amount.

    This path must fail closed: if Redis is unavailable, the upload route
    should stop before spending money on a new OCR request.
    """
    if estimated_jpy <= 0:
        return True
    if redis is None:
        logger.error("cost_guard redis unavailable during budget check")
        capture_message("cost_guard_unavailable", level="error")
        return False

    settings = get_settings()
    try:
        current = float(await redis.get(_daily_cost_key()) or 0.0)
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.error("cost_guard budget check failed: %s", exc)
        capture_message("cost_guard_unavailable", level="error")
        return False
    return (current + float(estimated_jpy)) <= float(settings.DAILY_COST_BUDGET_JPY)


async def record_cost(redis: Redis | None, actual_jpy: float) -> None:
    """Record realized OCR spend for today's budget ledger.

    This is best effort after a successful OCR call. We still log and surface
    the issue because losing these writes weakens future budget checks.
    """
    if actual_jpy <= 0 or redis is None:
        if actual_jpy > 0 and redis is None:
            logger.error("cost_guard redis unavailable during cost record")
            capture_message("cost_guard_unavailable", level="error")
        return

    key = _daily_cost_key()
    try:
        total = await redis.incrbyfloat(key, float(actual_jpy))
        if float(total) == float(actual_jpy):
            await redis.expire(key, 86_400)
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.error("cost_guard record_cost failed: %s", exc)
        capture_message("cost_guard_record_failed", level="error")


async def get_today_spent(redis: Redis | None) -> float:
    if redis is None:
        return 0.0
    try:
        return float(await redis.get(_daily_cost_key()) or 0.0)
    except _REDIS_FAILURE_EXCEPTIONS as exc:
        logger.warning("cost_guard get_today_spent failed: %s", exc)
        return 0.0
