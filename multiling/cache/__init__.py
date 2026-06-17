"""
cache.py - Multi-layer Caching System

Provides:
  - CacheEntry: Cache entry with TTL and metadata
  - MemoryCache: In-memory LRU cache
  - TimedCache: Time-based expiration cache
  - LayeredCache: Multi-layer cache (memory -> disk -> remote)
  - Cache metrics and monitoring
"""

import asyncio
import hashlib
import json
import os
import pickle
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A single cache entry with metadata"""
    key: str
    value: Any
    ttl: float = 0          
    created: float = field(default_factory=time.time)
    accessed: float = field(default_factory=time.time)
    hits: int = 0
    tags: List[str] = field(default_factory=list)
    priority: int = 0       

    def is_expired(self) -> bool:
        if self.ttl <= 0:
            return False
        return time.time() - self.created > self.ttl

    def to_dict(self) -> dict:
        return {
            "key": self.key, "ttl": self.ttl,
            "created": self.created, "accessed": self.accessed,
            "hits": self.hits, "tags": self.tags,
            "priority": self.priority,
            "expired": self.is_expired(),
        }


class MemoryCache:
    """Thread-safe in-memory LRU cache with TTL support"""

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0, "misses": 0, "sets": 0,
            "evictions": 0, "expirations": 0,
        }

    def get(self, key: str, default=None) -> Any:
        """Get value from cache, returns default if not found or expired"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return default
            if entry.is_expired():
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return default
            
            entry.accessed = time.time()
            entry.hits += 1
            self._stats["hits"] += 1
            
            self._cache.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl: float = None,
            tags: List[str] = None, priority: int = 0):
        """Set a cache entry"""
        if ttl is None:
            ttl = self.default_ttl
        entry = CacheEntry(
            key=key, value=value, ttl=ttl,
            tags=tags or [], priority=priority,
        )
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = entry
            
            while len(self._cache) > self.max_size:
                self._evict_one()
            self._stats["sets"] += 1

    def _evict_one(self):
        """Evict lowest priority / oldest entry"""
        
        for key, entry in self._cache.items():
            if entry.is_expired():
                del self._cache[key]
                self._stats["evictions"] += 1
                return
        
        min_priority = min(e.priority for e in self._cache.values())
        for key, entry in self._cache.items():
            if entry.priority == min_priority:
                del self._cache[key]
                self._stats["evictions"] += 1
                return
        
        self._cache.popitem(last=False)
        self._stats["evictions"] += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._stats["evictions"] += len(self._cache)

    def has(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired()

    def touch(self, key: str) -> bool:
        """Update access time without returning value"""
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                entry.accessed = time.time()
                entry.hits += 1
                self._cache.move_to_end(key)
                return True
            return False

    def get_stats(self) -> dict:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                "size": len(self._cache), "max_size": self.max_size,
                **self._stats, "hit_rate": round(hit_rate, 4),
            }

    def get_by_tag(self, tag: str) -> List[Tuple[str, Any]]:
        """Get all entries with a specific tag"""
        with self._lock:
            results = []
            for key, entry in self._cache.items():
                if tag in entry.tags and not entry.is_expired():
                    results.append((key, entry.value))
            return results

    def expire_check(self) -> int:
        """Manually expire old entries, returns count of expired"""
        count = 0
        with self._lock:
            expired_keys = [k for k, e in self._cache.items() if e.is_expired()]
            for k in expired_keys:
                del self._cache[k]
                count += 1
            self._stats["expirations"] += count
        return count


class TimedCache(MemoryCache):
    """Cache with automatic periodic cleanup"""

    def __init__(self, max_size=1000, default_ttl=300.0,
                 cleanup_interval=60.0):
        super().__init__(max_size, default_ttl)
        self.cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._auto_cleanup = True

    def get(self, key, default=None):
        
        if self._auto_cleanup and time.time() - self._last_cleanup > self.cleanup_interval:
            self.expire_check()
            self._last_cleanup = time.time()
        return super().get(key, default)


class LayeredCache:
    """
    Multi-layer cache: memory -> disk -> remote

    Reads cascade through layers, writes go to all layers.
    """

    def __init__(self, name="default", memory_max=1000, disk_path="./cache"):
        self.name = name
        self.memory = MemoryCache(max_size=memory_max)
        self.disk_path = disk_path
        os.makedirs(disk_path, exist_ok=True)
        self._stats = {"memory_hits": 0, "disk_hits": 0, "misses": 0}

    def _disk_key(self, key: str) -> str:
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.disk_path, f"{safe_key}.cache")

    def get(self, key: str, default=None) -> Any:
        
        val = self.memory.get(key)
        if val is not None:
            self._stats["memory_hits"] += 1
            return val

        
        disk_key = self._disk_key(key)
        if os.path.exists(disk_key):
            try:
                with open(disk_key, "rb") as f:
                    entry = pickle.load(f)
                if not entry.is_expired():
                    
                    self.memory.set(key, entry.value,
                                   ttl=entry.ttl, tags=entry.tags)
                    self._stats["disk_hits"] += 1
                    return entry.value
            except Exception:
                pass

        self._stats["misses"] += 1
        return default

    def set(self, key: str, value: Any, ttl: float = 300.0,
            tags: List[str] = None, priority: int = 0):
        
        self.memory.set(key, value, ttl=ttl, tags=tags, priority=priority)
        entry = CacheEntry(key=key, value=value, ttl=ttl,
                          tags=tags or [], priority=priority)
        disk_key = self._disk_key(key)
        try:
            with open(disk_key, "wb") as f:
                pickle.dump(entry, f)
        except Exception:
            pass

    def delete(self, key: str):
        self.memory.delete(key)
        disk_key = self._disk_key(key)
        if os.path.exists(disk_key):
            os.remove(disk_key)

    def clear(self):
        self.memory.clear()
        
        for f in os.listdir(self.disk_path):
            if f.endswith(".cache"):
                os.remove(os.path.join(self.disk_path, f))

    def get_stats(self) -> dict:
        mem_stats = self.memory.get_stats()
        total = self._stats["memory_hits"] + self._stats["disk_hits"] + self._stats["misses"]
        hit_rate = (self._stats["memory_hits"] + self._stats["disk_hits"]) / total if total > 0 else 0
        return {
            "layers": ["memory", "disk"],
            "stats": self._stats,
            "memory_stats": mem_stats,
            "overall_hit_rate": round(hit_rate, 4),
        }