"""
test_queue_cache.py — cover multiling/queue/*.py and multiling/cache/*.py

Tests cover:
  - FifoQueue enqueue then dequeue returns same item
  - FifoQueue FIFO order with 3+ items
  - PriorityQueue enqueue/dequeue respects priority
  - LruCache get on miss returns None
  - LruCache eviction drops least-recently-used when full
  - TtlCache entry expires after TTL (use monkeypatch time or short TTL)
"""
from __future__ import annotations

import time

import pytest

from multiling.queue.fifo import FIFOQueue
from multiling.queue.priority import PriorityQueue
from multiling.cache.lru import LRUCache
from multiling.cache.ttl import TTLCache


class TestFifoQueue:
    def test_enqueue_then_dequeue_returns_same_item(self):
        q = FIFOQueue()
        q.put("alpha")
        assert q.get() == "alpha"

    def test_dequeue_empty_returns_none(self):
        q = FIFOQueue()
        assert q.get() is None

    def test_fifo_order_with_three_items(self):
        q = FIFOQueue()
        q.put("first")
        q.put("second")
        q.put("third")
        assert q.get() == "first"
        assert q.get() == "second"
        assert q.get() == "third"

    def test_len_tracks_count(self):
        q = FIFOQueue()
        assert len(q) == 0
        q.put("a")
        assert len(q) == 1
        q.get()
        assert len(q) == 0

    def test_empty_method(self):
        q = FIFOQueue()
        assert q.empty() is True
        q.put("x")
        assert q.empty() is False


class TestPriorityQueue:
    def test_enqueue_dequeue_respects_priority(self):
        q = PriorityQueue()
        q.put("low", priority=10)
        q.put("high", priority=1)
        q.put("medium", priority=5)
        assert q.get() == "high"
        assert q.get() == "medium"
        assert q.get() == "low"

    def test_dequeue_empty_returns_none(self):
        q = PriorityQueue()
        assert q.get() is None

    def test_len_tracks_count(self):
        q = PriorityQueue()
        assert len(q) == 0
        q.put("a", priority=1)
        assert len(q) == 1
        q.get()
        assert len(q) == 0


class TestLruCache:
    def test_get_on_miss_returns_none(self):
        cache = LRUCache(capacity=2)
        assert cache.get("missing") is None

    def test_put_and_get_roundtrip(self):
        cache = LRUCache(capacity=2)
        cache.put("k", "v")
        assert cache.get("k") == "v"

    def test_eviction_drops_least_recently_used_when_full(self):
        cache = LRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        # Access 'a' to make 'b' the LRU
        cache.get("a")
        cache.put("c", 3)
        assert cache.get("a") == 1
        assert cache.get("b") is None  # evicted
        assert cache.get("c") == 3

    def test_len_tracks_size(self):
        cache = LRUCache(capacity=3)
        assert len(cache) == 0
        cache.put("x", 1)
        assert len(cache) == 1
        cache.clear()
        assert len(cache) == 0


class TestTtlCache:
    def test_get_returns_none_after_expiry(self, monkeypatch):
        cache = TTLCache(default_ttl=0.05)
        cache.put("k", "v")
        assert cache.get("k") == "v"
        original_time = time.time
        monkeypatch.setattr(time, "time", lambda: original_time() + 0.2)
        assert cache.get("k") is None

    def test_get_returns_value_before_expiry(self, monkeypatch):
        cache = TTLCache(default_ttl=10.0)
        cache.put("k", "v")
        original_time = time.time
        monkeypatch.setattr(time, "time", lambda: original_time() + 1.0)
        assert cache.get("k") == "v"

    def test_clear_removes_all_entries(self):
        cache = TTLCache()
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_custom_ttl_per_entry(self, monkeypatch):
        cache = TTLCache(default_ttl=10.0)
        cache.put("short", "v", ttl=0.05)
        cache.put("long", "v", ttl=100.0)
        original_time = time.time
        monkeypatch.setattr(time, "time", lambda: original_time() + 0.1)
        assert cache.get("short") is None
        assert cache.get("long") == "v"
