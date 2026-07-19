"""
MINXG Caching — Multi-level caching for LLM responses.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import hashlib
import time
import json
from pathlib import Path


@dataclass
class CacheEntry:
    """A cached response."""
    key: str
    content: str
    model: str
    created_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    tokens: int = 0
    cost_saved: float = 0.0


class SemanticCache:
    """
    Semantic cache using embedding similarity.

    Caches responses based on semantic similarity of prompts,
    not exact string matching.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.95,
        max_entries: int = 10000,
        ttl_seconds: int = 86400 * 7,  # 7 days
    ):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.entries: Dict[str, CacheEntry] = {}
        self.index: Dict[str, List[float]] = {}  # prompt_hash -> embedding

    def get(
        self,
        prompt: str,
        model: str = "gpt-4o",
        embedding: Optional[List[float]] = None,
    ) -> Optional[str]:
        """Get cached response for a prompt."""
        key = self._make_key(prompt, model)

        if key in self.entries:
            entry = self.entries[key]
            if not self._is_expired(entry):
                entry.access_count += 1
                entry.last_accessed = time.time()
                return entry.content

        # Try semantic similarity
        if embedding and self.index:
            best_match = self._find_similar(embedding, model)
            if best_match:
                return best_match.content

        return None

    def set(
        self,
        prompt: str,
        response: str,
        model: str = "gpt-4o",
        embedding: Optional[List[float]] = None,
        tokens: int = 0,
    ) -> None:
        """Cache a response."""
        key = self._make_key(prompt, model)

        if len(self.entries) >= self.max_entries:
            self._evict()

        # Estimate cost savings
        cost_per_1k = {"gpt-4o": 0.03, "gpt-4": 0.06, "gpt-3.5-turbo": 0.001}.get(model, 0.002)
        cost_saved = (tokens / 1000) * cost_per_1k

        entry = CacheEntry(
            key=key,
            content=response,
            model=model,
            created_at=time.time(),
            tokens=tokens,
            cost_saved=cost_saved,
        )
        self.entries[key] = entry

        if embedding is not None:
            self.index[key] = embedding

    def clear(self) -> None:
        """Clear all cached entries."""
        self.entries = {}
        self.index = {}

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_tokens = sum(e.tokens for e in self.entries.values())
        total_cost_saved = sum(e.cost_saved for e in self.entries.values())
        hit_rate = sum(e.access_count for e in self.entries.values())

        return {
            "total_entries": len(self.entries),
            "max_entries": self.max_entries,
            "total_tokens_cached": total_tokens,
            "total_cost_saved": total_cost_saved,
            "cache_hits": hit_rate,
            "hit_rate_percent": (hit_rate / max(1, hit_rate + len(self.entries))) * 100,
        }

    def _make_key(self, prompt: str, model: str) -> str:
        """Create cache key from prompt and model."""
        return hashlib.sha256(f"{prompt}:{model}".encode()).hexdigest()[:16]

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry is expired."""
        return time.time() - entry.created_at > self.ttl_seconds

    def _find_similar(
        self,
        query_embedding: List[float],
        model: str,
    ) -> Optional[CacheEntry]:
        """Find semantically similar cached entry."""
        best_score = 0
        best_entry = None

        for key, embedding in self.index.items():
            if key not in self.entries:
                continue
            entry = self.entries[key]
            if entry.model != model:
                continue
            if self._is_expired(entry):
                continue

            score = self._cosine_similarity(query_embedding, embedding)
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_entry = entry

        if best_entry:
            best_entry.access_count += 1
            best_entry.last_accessed = time.time()

        return best_entry

    def _evict(self) -> None:
        """Evict oldest entries."""
        # Remove expired first
        expired = [k for k, e in self.entries.items() if self._is_expired(e)]
        for k in expired:
            del self.entries[k]
            self.index.pop(k, None)

        # If still over limit, remove least accessed
        if len(self.entries) > self.max_entries:
            sorted_entries = sorted(
                self.entries.items(),
                key=lambda x: x[1].access_count,
            )
            to_remove = len(self.entries) - self.max_entries
            for k, _ in sorted_entries[:to_remove]:
                del self.entries[k]
                self.index.pop(k, None)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0
        return dot / (norm_a * norm_b)


class TieredCache:
    """
    Multi-tier caching: L1 (memory) -> L2 (disk) -> L3 (remote).
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.l1: Dict[str, CacheEntry] = {}  # In-memory
        self.l1_max = 1000

        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".minxg" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.l2_index: Dict[str, str] = self._load_l2_index()

    def get(self, key: str) -> Optional[str]:
        """Get from cache (L1 first, then L2)."""
        # L1 check
        if key in self.l1:
            entry = self.l1[key]
            entry.access_count += 1
            return entry.content

        # L2 check
        if key in self.l2_index:
            file_path = self.cache_dir / self.l2_index[key]
            if file_path.exists():
                content = file_path.read_text()
                # Promote to L1
                self._l1_set(key, content)
                return content

        return None

    def set(self, key: str, value: str, tier: str = "auto") -> None:
        """Set in cache."""
        if tier in ("l1", "auto"):
            self._l1_set(key, value)

        if tier in ("l2", "auto"):
            self._l2_set(key, value)

    def _l1_set(self, key: str, value: str) -> None:
        """Set in L1 cache."""
        if len(self.l1) >= self.l1_max:
            # Evict least recently used
            lru_key = min(self.l1, key=lambda k: self.l1[k].last_accessed)
            del self.l1[lru_key]

        self.l1[key] = CacheEntry(
            key=key,
            content=value,
            model="cached",
            created_at=time.time(),
            last_accessed=time.time(),
        )

    def _l2_set(self, key: str, value: str) -> None:
        """Set in L2 (disk) cache."""
        filename = hashlib.md5(key.encode()).hexdigest()
        file_path = self.cache_dir / filename
        file_path.write_text(value)
        self.l2_index[key] = filename
        self._save_l2_index()

    def _load_l2_index(self) -> Dict[str, str]:
        """Load L2 index from disk."""
        index_file = self.cache_dir / "l2_index.json"
        if index_file.exists():
            return json.loads(index_file.read_text())
        return {}

    def _save_l2_index(self) -> None:
        """Save L2 index to disk."""
        index_file = self.cache_dir / "l2_index.json"
        index_file.write_text(json.dumps(self.l2_index))

    def clear(self) -> None:
        """Clear all cache tiers."""
        self.l1 = {}
        self.l2_index = {}
        for f in self.cache_dir.glob("*"):
            if f.name != "l2_index.json":
                f.unlink()
        self._save_l2_index()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        l2_size = sum(f.stat().st_size for f in self.cache_dir.glob("*") if f.name != "l2_index.json")
        return {
            "l1_entries": len(self.l1),
            "l1_max": self.l1_max,
            "l2_entries": len(self.l2_index),
            "l2_size_bytes": l2_size,
            "l2_size_mb": l2_size / (1024 * 1024),
        }


class CacheMiddleware:
    """
    Middleware for caching LLM API responses.

    Wraps API calls with automatic caching.
    """

    def __init__(
        self,
        cache: Optional[SemanticCache] = None,
        enabled: bool = True,
    ):
        self.cache = cache or SemanticCache()
        self.enabled = enabled
        self.stats = {
            "hits": 0,
            "misses": 0,
            "savings": 0.0,
        }

    def call(
        self,
        prompt: str,
        llm_call: callable,
        model: str = "gpt-4o",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Call LLM with caching.

        Args:
            prompt: Input prompt.
            llm_call: Function to call if cache miss.
            model: Model name.
            **kwargs: Additional arguments for llm_call.

        Returns:
            LLM response dict.
        """
        if not self.enabled:
            return llm_call(prompt, **kwargs)

        # Try cache
        cached = self.cache.get(prompt, model)
        if cached:
            self.stats["hits"] += 1
            return {
                "cached": True,
                "content": cached,
                "usage": {"total_tokens": 0},
            }

        # Cache miss - call LLM
        self.stats["misses"] += 1
        response = llm_call(prompt, **kwargs)

        # Store in cache
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        tokens = response.get("usage", {}).get("total_tokens", 0)
        self.cache.set(prompt, content, model, tokens=tokens)
        self.stats["savings"] += self.cache.entries[self.cache._make_key(prompt, model)].cost_saved

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get middleware statistics."""
        cache_stats = self.cache.stats()
        return {
            **cache_stats,
            "api_hits": self.stats["hits"],
            "api_misses": self.stats["misses"],
            "hit_rate": self.stats["hits"] / max(1, self.stats["hits"] + self.stats["misses"]),
            "total_savings": self.stats["savings"],
        }
