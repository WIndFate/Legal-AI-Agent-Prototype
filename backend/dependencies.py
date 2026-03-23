from redis.asyncio import Redis

from backend.config import get_settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    """Get async Redis client singleton."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis
