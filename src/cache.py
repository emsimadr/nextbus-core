"""
In-memory TTL cache with stale grace period.

Generic cache -- not MBTA-specific. Stores any value by string key
with configurable fresh TTL and stale grace period.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CacheEntry:
    """A cached value with its storage timestamp."""

    value: Any
    stored_at: float  # time.monotonic() when stored

    def age(self, now: Optional[float] = None) -> float:
        """Seconds since this entry was stored."""
        if now is None:
            now = time.monotonic()
        return now - self.stored_at


class TTLCache:
    """
    Simple in-memory cache with TTL and stale grace period.

    - get(): returns value if within TTL (fresh hit).
    - get_stale(): returns value if within stale_max_age (stale hit).
    - set(): stores a value with current timestamp.
    """

    def __init__(self, ttl: float, stale_max_age: float) -> None:
        self._ttl = ttl
        self._stale_max_age = stale_max_age
        self._store: dict[str, CacheEntry] = {}
        self._clock = time.monotonic  # overridable for testing

    def get(self, key: str) -> Optional[CacheEntry]:
        """Return the entry if it exists and is within TTL."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.age(self._clock()) > self._ttl:
            return None
        return entry

    def get_stale(self, key: str) -> Optional[CacheEntry]:
        """Return the entry if it exists and is within stale_max_age."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.age(self._clock()) > self._stale_max_age:
            return None
        return entry

    def set(self, key: str, value: Any) -> None:
        """Store a value with the current timestamp."""
        self._store[key] = CacheEntry(value=value, stored_at=self._clock())

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()
