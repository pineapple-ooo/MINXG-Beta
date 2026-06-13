"""cache.ttl — Time-to-live cache with sliding/absolute expiry modes.""""
from __future__ import annotations
import time
from threading import RLock
from typing import Any, Dict, Iterator, Optional, Tuple


class TTLCache:
    def __init__(self, default_ttl: float = 60.0) -> None:
        self._cache: Dict[Any, Tuple[Any, float]] = {}
        self._default_ttl = float(default_ttl)
        self._lock = RLock()

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return default
            value, expires = entry
            if time.time() >= expires:
                self._cache.pop(key, None)
                return default
            return value

    def put(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        ttl = float(ttl) if ttl is not None else self._default_ttl
        with self._lock:
            self._cache[key] = (value, time.time() + ttl)

    def touch(self, key: Any, ttl: Optional[float] = None) -> bool:
        ttl = float(ttl) if ttl is not None else self._default_ttl
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return False
            value, _ = entry
            self._cache[key] = (value, time.time() + ttl)
            return True

    def discard(self, key: Any) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def purge_expired(self) -> int:
        with self._lock:
            now = time.time()
            expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
            for k in expired:
                self._cache.pop(k, None)
            return len(expired)

    def keys(self) -> Iterator[Any]:
        with self._lock:
            return iter(list(self._cache.keys()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)
