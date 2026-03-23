import json
import logging

from backend.dependencies import get_redis

logger = logging.getLogger(__name__)

# Reports expire after 24 hours
REPORT_TTL_SECONDS = 24 * 60 * 60


def _cache_key(order_id: str) -> str:
    return f"report:{order_id}"


async def cache_report(order_id: str, report_data: dict) -> None:
    """Store report in Redis with 24h TTL."""
    redis = await get_redis()
    key = _cache_key(order_id)
    await redis.set(key, json.dumps(report_data, ensure_ascii=False), ex=REPORT_TTL_SECONDS)
    logger.info("Cached report for order %s (TTL=%ds)", order_id, REPORT_TTL_SECONDS)


async def get_cached_report(order_id: str) -> dict | None:
    """Retrieve report from Redis cache. Returns None if expired or missing."""
    redis = await get_redis()
    data = await redis.get(_cache_key(order_id))
    if data is None:
        return None
    return json.loads(data)


async def delete_cached_report(order_id: str) -> None:
    """Explicitly remove a report from cache."""
    redis = await get_redis()
    await redis.delete(_cache_key(order_id))
