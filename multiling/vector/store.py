"""Vector store — see __init__.py."""
import math
from typing import List, Tuple

class VectorStore:
    def __init__(self, dim: int):
        self._dim = dim
        self._vecs: List[Tuple[str, List[float]]] = []
    def add_vector(self, vid, vec):
        if len(vec) != self._dim: return False
        self._vecs.append((vid, vec))
        return True
    def search(self, query, k=5):
        scored = []
        for vid, v in self._vecs:
            d = math.sqrt(sum((a-b)**2 for a, b in zip(query, v)))
            scored.append((vid, d))
        scored.sort(key=lambda x: x[1])
        return scored[:k]

add_vector = VectorStore(0).add_vector
search = VectorStore(0).search
