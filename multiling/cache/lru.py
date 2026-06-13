"""cache.lru — Least-Recently-Used cache with hit/miss accounting.

`stats()` exposes hit/miss/evict counters; useful in tests and for
exposing cache effectiveness to observability cells.
""""
from __future__ import annotations
from collections import OrderedDict
from threading import RLock
from typing import Any, Iterator, Optional, Tuple


class LRUCache:
    def __init__(self, capacity: int = 128) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._cache: "OrderedDict[Any, Any]" = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return default

    def put(self, key: Any, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
                return
            self._cache[key] = value
            if len(self._cache) > self._capacity:
                self._cache.popitem(last=False)
                self._evictions += 1

    def discard(self, key: Any) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = self._misses = self._evictions = 0

    def keys(self) -> Iterator[Any]:
        with self._lock:
            return iter(list(self._cache.keys()))

    def stats(self) -> Tuple[int, int, int, int]:
        with self._lock:
            return self._hits, self._misses, self._evictions, len(self._cache)

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._cache
