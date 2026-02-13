"""Tests for in-memory TTL cache."""

from src.cache import TTLCache


class FakeClock:
    """Controllable clock for deterministic cache tests."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestTTLCache:
    def _make_cache(self, ttl=20.0, stale_max_age=300.0):
        clock = FakeClock()
        cache = TTLCache(ttl=ttl, stale_max_age=stale_max_age)
        cache._clock = clock
        return cache, clock

    def test_set_and_get_within_ttl(self):
        cache, clock = self._make_cache(ttl=20)
        cache.set("k1", {"data": "hello"})
        entry = cache.get("k1")
        assert entry is not None
        assert entry.value == {"data": "hello"}

    def test_get_returns_none_after_ttl(self):
        cache, clock = self._make_cache(ttl=20)
        cache.set("k1", "value")
        clock.advance(21)
        assert cache.get("k1") is None

    def test_get_returns_entry_at_ttl_boundary(self):
        cache, clock = self._make_cache(ttl=20)
        cache.set("k1", "value")
        clock.advance(20)
        # Exactly at TTL -- age == ttl, which is NOT > ttl, so still valid
        assert cache.get("k1") is not None

    def test_get_stale_within_grace(self):
        cache, clock = self._make_cache(ttl=20, stale_max_age=300)
        cache.set("k1", "value")
        clock.advance(60)  # Past TTL but within stale_max_age
        assert cache.get("k1") is None  # Fresh get fails
        entry = cache.get_stale("k1")
        assert entry is not None
        assert entry.value == "value"

    def test_get_stale_expired(self):
        cache, clock = self._make_cache(ttl=20, stale_max_age=300)
        cache.set("k1", "value")
        clock.advance(301)  # Past stale_max_age
        assert cache.get_stale("k1") is None

    def test_cold_start_empty(self):
        cache, clock = self._make_cache()
        assert cache.get("nonexistent") is None
        assert cache.get_stale("nonexistent") is None

    def test_overwrite_resets_timestamp(self):
        cache, clock = self._make_cache(ttl=20)
        cache.set("k1", "old")
        clock.advance(15)
        cache.set("k1", "new")
        clock.advance(10)  # 10s after overwrite, 25s after first set
        entry = cache.get("k1")
        assert entry is not None  # Still within TTL of overwrite
        assert entry.value == "new"

    def test_clear_removes_all(self):
        cache, clock = self._make_cache()
        cache.set("k1", "a")
        cache.set("k2", "b")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None

    def test_multiple_keys_independent(self):
        cache, clock = self._make_cache(ttl=20)
        cache.set("k1", "a")
        clock.advance(10)
        cache.set("k2", "b")
        clock.advance(15)
        # k1 is 25s old (expired), k2 is 15s old (fresh)
        assert cache.get("k1") is None
        assert cache.get("k2") is not None

    def test_entry_age(self):
        cache, clock = self._make_cache()
        cache.set("k1", "val")
        clock.advance(42)
        entry = cache.get_stale("k1")
        assert entry is not None
        assert entry.age(clock()) == 42.0
