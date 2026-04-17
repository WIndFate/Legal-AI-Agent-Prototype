from __future__ import annotations

import asyncio

import pytest

from backend.services.cost_guard import check_budget_allowed, get_today_spent, record_cost


class FakeRedis:
    def __init__(self, *, fail: bool = False):
        self.store: dict[str, float] = {}
        self.fail = fail

    async def get(self, key):
        if self.fail:
            raise RuntimeError("redis down")
        return self.store.get(key)

    async def incrbyfloat(self, key, amount):
        if self.fail:
            raise RuntimeError("redis down")
        self.store[key] = float(self.store.get(key, 0.0)) + float(amount)
        return self.store[key]

    async def expire(self, key, seconds):  # noqa: ARG002
        return True


@pytest.mark.asyncio
async def test_check_budget_allowed_accepts_when_under_limit():
    redis = FakeRedis()
    await record_cost(redis, 100.0)

    allowed = await check_budget_allowed(redis, 50.0)

    assert allowed is True
    assert await get_today_spent(redis) == 100.0


@pytest.mark.asyncio
async def test_check_budget_allowed_rejects_when_over_limit():
    redis = FakeRedis()
    await record_cost(redis, 499.0)

    allowed = await check_budget_allowed(redis, 2.0)

    assert allowed is False


@pytest.mark.asyncio
async def test_check_budget_allowed_fails_closed_when_redis_unavailable():
    redis = FakeRedis(fail=True)

    allowed = await check_budget_allowed(redis, 1.0)

    assert allowed is False


class TimeoutRedis:
    async def get(self, key):  # noqa: ARG002
        raise asyncio.TimeoutError("redis timeout")


@pytest.mark.asyncio
async def test_check_budget_allowed_fails_closed_when_redis_times_out():
    allowed = await check_budget_allowed(TimeoutRedis(), 1.0)

    assert allowed is False
