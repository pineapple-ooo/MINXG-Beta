"""LRU cache — see __init__.py."""
from collections import OrderedDict
from typing import Any

class LRUCache:
    def __init__(self, capacity: int = 128):
        self._cache = OrderedDict()
        self._capacity = capacity
    def get(self, key):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    def put(self, key, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._capacity:
            self._cache.popitem(last=False)
    def __len__(self): return len(self._cache)
    def clear(self): self._cache.clear()
