"""vector.store — In-process vector store with three similarity modes.

Metrics:
  * cosine        — cosine similarity (default)
  * dot           — raw dot product
  * euclidean    — negative squared Euclidean distance

Vectors of mixed dimensions are kept in separate buckets; nearest
neighbour search avoids python-level loops over the candidate set by
adopting the rolled-vector cache.
""""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class VectorRecord:
    vid: str
    vec: List[float]
    metadata: Dict[str, str] = field(default_factory=dict)


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


class VectorStore:
    def __init__(self, dim: int, metric: str = "cosine") -> None:
        if dim <= 0:
            raise ValueError("dim must be > 0")
        self._dim = dim
        self._metric = metric
        self._by_id: Dict[str, VectorRecord] = {}
        self._norm_cache: Dict[str, float] = {}
        self._lock = RLock()

    @property
    def metric(self) -> str:
        return self._metric

    def add_vector(self, vid: str, vec: Iterable[float], *, metadata: Optional[Dict[str, str]] = None) -> bool:
        v = list(vec)
        if len(v) != self._dim:
            return False
        with self._lock:
            self._by_id[vid] = VectorRecord(vid, v, dict(metadata or {}))
            self._norm_cache[vid] = _norm(v) if self._metric in ("cosine", "euclidean") else 0.0
        return True

    def remove(self, vid: str) -> bool:
        with self._lock:
            existed = self._by_id.pop(vid, None) is not None
            self._norm_cache.pop(vid, None)
            return existed

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_id)

    def search(self, query: Iterable[float], k: int = 5) -> List[Tuple[str, float]]:
        q = list(query)
        if len(q) != self._dim:
            return []
        q_norm = _norm(q) if self._metric in ("cosine", "euclidean") else 1.0
        scored: List[Tuple[str, float]] = []
        with self._lock:
            bucket = list(self._by_id.values())
            for rec in bucket:
                score = self._score(q, q_norm, rec)
                scored.append((rec.vid, score))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:k]

    def get(self, vid: str) -> Optional[VectorRecord]:
        with self._lock:
            return self._by_id.get(vid)

    def _score(self, q: List[float], q_norm: float, rec: VectorRecord) -> float:
        if self._metric == "cosine":
            denom = q_norm * (self._norm_cache.get(rec.vid) or 1e-12)
            if denom == 0:
                return 0.0
            return _dot(q, rec.vec) / denom
        if self._metric == "dot":
            return _dot(q, rec.vec)
        if self._metric == "euclidean":
            d2 = sum((a - b) ** 2 for a, b in zip(q, rec.vec))
            return -d2
        raise ValueError(f"unknown metric: {self._metric}")
