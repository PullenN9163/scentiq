"""A small, thread-safe, bounded cache with a time-to-live."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from threading import Lock


class TtlLruCache[V]:
    """Least-recently-used entries expire after `ttl_seconds` and the cache holds at most
    `max_entries`. Entries are keyed by the caller, so a key that includes a version
    number makes stale values unreachable rather than needing invalidation."""

    def __init__(
        self,
        max_entries: int,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1 or ttl_seconds <= 0:
            raise ValueError("max_entries and ttl_seconds must be positive")
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._clock = clock
        self._items: OrderedDict[Hashable, tuple[float, V]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: Hashable) -> V | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at >= self._ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def put(self, key: Hashable, value: V) -> None:
        with self._lock:
            self._items[key] = (self._clock(), value)
            self._items.move_to_end(key)
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
