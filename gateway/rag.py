"""


"""
from __future__ import annotations
import math
import re
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: List[str] = []
        self._tokens_list: List[List[str]] = []
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._avgdl: float = 0.0
        self._doc_len: List[int] = []

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower())

    def add_document(self, doc_id: str, text: str) -> None:
        tokens = self._tokenize(text)
        self._docs.append(doc_id)
        self._tokens_list.append(tokens)
        self._doc_len.append(len(tokens))
        # update df
        for tok in set(tokens):
            self._df[tok] = self._df.get(tok, 0) + 1
        self._avgdl = sum(self._doc_len) / len(self._doc_len) if self._doc_len else 0
        # update idf
        N = len(self._docs)
        for tok, df in self._df.items():
            self._idf[tok] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        q_tokens = self._tokenize(query)
        scores: Dict[int, float] = {}
        for idx, tokens in enumerate(self._tokens_list):
            score = 0.0
            doc_len = self._doc_len[idx]
            tf_counter = Counter(tokens)
            for qt in q_tokens:
                if qt not in self._idf:
                    continue
                tf = tf_counter.get(qt, 0)
                idf = self._idf[qt]
                denom = tf + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl)
                score += idf * (tf * (self.k1 + 1)) / denom if denom else 0
            if score > 0:
                scores[idx] = score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self._docs[idx], score) for idx, score in sorted_scores]


class SemanticIndex:
    def __init__(self):
        self._docs: List[str] = []
        self._vectors: List[Counter] = []

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower())

    def add_document(self, doc_id: str, text: str) -> None:
        tokens = self._tokenize(text)
        self._docs.append(doc_id)
        self._vectors.append(Counter(tokens))

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        q_tokens = self._tokenize(query)
        q_vec = Counter(q_tokens)
        q_norm = math.sqrt(sum(v ** 2 for v in q_vec.values()))
        results = []
        for idx, vec in enumerate(self._vectors):
            dot = sum(q_vec[t] * vec[t] for t in q_vec)
            d_norm = math.sqrt(sum(v ** 2 for v in vec.values()))
            if q_norm and d_norm:
                sim = dot / (q_norm * d_norm)
                if sim > 0:
                    results.append((self._docs[idx], sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class HybridRAG:
    """
    """
    def __init__(self, bm25_weight: float = 0.6, semantic_weight: float = 0.4):
        self.bm25 = BM25Index()
        self.semantic = SemanticIndex()
        self._contents: Dict[str, str] = {}
        self.bm25_weight = bm25_weight
        self.semantic_weight = semantic_weight

    def add_chunk(self, chunk_id: str, text: str) -> None:
        self._contents[chunk_id] = text
        self.bm25.add_document(chunk_id, text)
        self.semantic.add_document(chunk_id, text)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        bm25_results = {doc_id: score for doc_id, score in self.bm25.search(query, top_k=top_k * 2)}
        sem_results = {doc_id: score for doc_id, score in self.semantic.search(query, top_k=top_k * 2)}

        all_ids = set(bm25_results.keys()) | set(sem_results.keys())
        fused = []
        for doc_id in all_ids:
            b_score = bm25_results.get(doc_id, 0)
            s_score = sem_results.get(doc_id, 0)
            max_b = max(bm25_results.values()) if bm25_results else 1
            max_s = max(sem_results.values()) if sem_results else 1
            combined = (b_score / max_b) * self.bm25_weight + (s_score / max_s) * self.semantic_weight
            fused.append((doc_id, combined))

        fused.sort(key=lambda x: x[1], reverse=True)
        results = []
        for doc_id, score in fused[:top_k]:
            results.append({
                "id": doc_id,
                "score": round(score, 4),
                "content": self._contents.get(doc_id, "")[:1500],
            })
        return results

    def inject_context(self, query: str, max_tokens: int = 1500) -> str:
        chunks = self.search(query, top_k=3)
        if not chunks:
            return ""
        parts = ["# Relevant Knowledge"]
        total_len = 0
        for c in chunks:
            piece = f"\n[{c['id']}] (score: {c['score']})\n{c['content']}"
            if total_len + len(piece) > max_len:
                break
            parts.append(piece)
            total_len += len(piece)
        return "\n".join(parts)

    def clear(self) -> None:
        self.__init__(self.bm25_weight, self.semantic_weight)
