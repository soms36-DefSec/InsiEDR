"""
tests/test_redis_cache.py
-------------------------
Unit tests for the Redis 7 TieredCache, L1/L2 fallbacks, and @cached decorator.
"""
import time
import pytest
from unittest.mock import MagicMock, patch

from server.api.cache import (
    InMemoryCacheProvider,
    Redis7CacheProvider,
    TieredCache,
    cached,
)


def test_in_memory_cache_get_set_ttl():
    cache = InMemoryCacheProvider(default_ttl=0.2, max_items=10)
    cache.set("foo", {"bar": 123}, ttl=0.2)
    assert cache.get("foo") == {"bar": 123}
    assert cache.get("non_existent") is None

    # Wait for TTL expiry
    time.sleep(0.25)
    assert cache.get("foo") is None


def test_in_memory_cache_lru_eviction():
    cache = InMemoryCacheProvider(default_ttl=60.0, max_items=2)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    # Access k1 so k2 becomes least recently used
    _ = cache.get("k1")
    cache.set("k3", "v3")

    assert cache.get("k1") == "v1"
    assert cache.get("k3") == "v3"
    assert cache.get("k2") is None


def test_in_memory_cache_pattern_invalidation():
    cache = InMemoryCacheProvider(default_ttl=60.0)
    cache.set("user:1:profile", "p1")
    cache.set("user:2:profile", "p2")
    cache.set("fleet:status", "active")

    deleted = cache.clear_pattern("user:*")
    assert deleted == 2
    assert cache.get("user:1:profile") is None
    assert cache.get("user:2:profile") is None
    assert cache.get("fleet:status") == "active"


def test_tiered_cache_fallback_when_redis_offline():
    # Intentionally invalid Redis URL
    tiered = TieredCache(redis_url="redis://nonexistent-host:9999/0", default_ttl=5.0)
    # Must function smoothly using L1 in-memory
    tiered.set("test_key", {"fleet_count": 42}, ttl=5.0)
    assert tiered.get("test_key") == {"fleet_count": 42}
    tiered.invalidate("test_key")
    assert tiered.get("test_key") is None


def test_cached_decorator_sync():
    calls = 0

    @cached(ttl=1.0, key_prefix="test_sync")
    def compute_data(x: int):
        nonlocal calls
        calls += 1
        return x * 2

    res1 = compute_data(5)
    res2 = compute_data(5)
    assert res1 == 10
    assert res2 == 10
    assert calls == 1  # Second call was served from cache


@pytest.mark.asyncio
async def test_cached_decorator_async():
    calls = 0

    @cached(ttl=1.0, key_prefix="test_async")
    async def fetch_async_data(agent_id: str):
        nonlocal calls
        calls += 1
        return {"agent": agent_id, "score": 99.0}

    res1 = await fetch_async_data("agent-101")
    res2 = await fetch_async_data("agent-101")
    assert res1 == {"agent": "agent-101", "score": 99.0}
    assert res2 == {"agent": "agent-101", "score": 99.0}
    assert calls == 1
