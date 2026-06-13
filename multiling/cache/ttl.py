"""TTL cache — see __init__.py."""
import time
from typing import Any, Dict, Tuple

class TTLCache:
    def __init__(self, default_ttl: float = 60.0):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._default_ttl = default_ttl
    def get(self, key):
        if key in self._cache:
            value, expires = self._cache[key]
            if time.time() < expires:
                return value
            del self._cache[key]
        return None
    def put(self, key, value, ttl=None):
        ttl = ttl or self._default_ttl
        self._cache[key] = (value, time.time() + ttl)
    def clear(self): self._cache.clear()
