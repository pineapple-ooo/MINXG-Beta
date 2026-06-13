"""knowledge.base — In-memory KB with three indexes: TF-IDF, Jaccard, prefix.

Scoring:
  * TF-IDF (BM25-ish) for main ranking
  * Prefix index for as-you-type completion
  * Jaccard fallback for very short queries
""""
from __future__ import annotations
import math
import re
from collections import defaultdict
from threading import RLock
from typing import Dict, List, Optional, Set, Tuple

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def _tokenise(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class KnowledgeBase:
    def __init__(self) -> None:
        self._docs: Dict[str, str] = {}
        self._index: Dict[str, Dict[str, int]] = defaultdict(dict)
        self._doc_len: Dict[str, int] = {}
        self._prefix: Dict[str, Set[str]] = defaultdict(set)
        self._lock = RLock()

    def add_document(self, doc_id: str, content: str) -> None:
        with self._lock:
            self.remove_document(doc_id)
            tokens = _tokenise(content)
            self._docs[doc_id] = content
            self._doc_len[doc_id] = len(tokens)
            tf: Dict[str, int] = defaultdict(int)
            for tok in tokens:
                tf[tok] += 1
                if len(tok) >= 3:
                    self._prefix[tok[:3]].add(doc_id)
            for tok, freq in tf.items():
                self._index[tok][doc_id] = freq

    def remove_document(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id not in self._docs:
                return False
            for tok in list(self._index.keys()):
                self._index[tok].pop(doc_id, None)
                if not self._index[tok]:
                    del self._index[tok]
            for prefix in list(self._prefix.keys()):
                self._prefix[prefix].discard(doc_id)
                if not self._prefix[prefix]:
                    del self._prefix[prefix]
            self._docs.pop(doc_id, None)
            self._doc_len.pop(doc_id, None)
            return True

    def get(self, doc_id: str) -> Optional[str]:
        with self._lock:
            return self._docs.get(doc_id)

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        q_tokens = _tokenise(query)
        if not q_tokens:
            return []
        scores: Dict[str, float] = defaultdict(float)
        avg_len = sum(self._doc_len.values()) / max(1, len(self._doc_len))
        k1, b = 1.2, 0.75
        with self._lock:
            n_docs = max(1, len(self._docs))
            for qt in q_tokens:
                postings = self._index.get(qt, {})
                df = len(postings)
                if df == 0:
                    continue
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                for doc_id, tf in postings.items():
                    dl = self._doc_len.get(doc_id, 1)
                    denom = tf + k1 * (1 - b + b * dl / max(1.0, avg_len))
                    scores[doc_id] += idf * (tf * (k1 + 1)) / denom
            if not scores and self._docs:
                q_set = set(q_tokens)
                for did, content in self._docs.items():
                    d_set = set(_tokenise(content))
                    if q_set and d_set:
                        scores[did] = len(q_set & d_set) / len(q_set | d_set)
            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            return ranked[:k]

    def autocomplete(self, prefix: str, limit: int = 8) -> List[str]:
        if not prefix or len(prefix) < 2:
            return []
        prefix = prefix.lower()
        prefix_key = prefix[:3]
        with self._lock:
            direct = list(self._prefix.get(prefix_key, ()))
            if not direct:
                return []
            results: List[Tuple[str, int]] = []
            for did in direct:
                tokens = set(_tokenise(self._docs.get(did, "")))
                hits = sum(1 for tok in tokens if tok.startswith(prefix))
                if hits:
                    results.append((did, hits))
            results.sort(key=lambda kv: kv[1], reverse=True)
            return [did for did, _ in results[:limit]]

    def __len__(self) -> int:
        with self._lock:
            return len(self._docs)
