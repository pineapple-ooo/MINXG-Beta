"""
vector.py — 向量存储与语义检索模块

提供轻量级向量存储，支持嵌入向量的增删改查和语义相似度搜索。
无需外部向量数据库依赖，纯 Python 实现（可扩展至 Milvus/FAISS/Pinecone）。
"""

import json
import math
import os
import pickle
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass
class VectorRecord:
    """向量记录"""
    id: str = field(default_factory=lambda: f"vec_{uuid.uuid4().hex[:12]}")
    vector: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "vector": self.vector,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class CosineSimilarity:
    """余弦相似度计算"""

    @staticmethod
    def compute(a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        if len(a) != len(b):
            raise ValueError(f"维度不匹配: {len(a)} vs {len(b)}")
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def batch_query(query_vec: List[float],
                    candidates: List[Tuple[str, List[float]]],
                    top_k: int = 10) -> List[Tuple[str, float]]:
        """批量计算相似度并返回 top_k 结果"""
        scores = []
        for vid, vec in candidates:
            sim = CosineSimilarity.compute(query_vec, vec)
            scores.append((vid, sim))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


class EuclideanDistance:
    """欧几里得距离计算"""

    @staticmethod
    def compute(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            raise ValueError(f"维度不匹配: {len(a)} vs {len(b)}")
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    @staticmethod
    def batch_query(query_vec: List[float],
                    candidates: List[Tuple[str, List[float]]],
                    top_k: int = 10) -> List[Tuple[str, float]]:
        scores = []
        for vid, vec in candidates:
            dist = EuclideanDistance.compute(query_vec, vec)
            scores.append((vid, dist))
        scores.sort(key=lambda x: x[1])  
        return scores[:top_k]


class VectorStore:
    """
    内存向量存储

    特性:
    - 多种距离度量（余弦/欧氏/点积）
    - 元数据过滤
    - 命名空间隔离
    - 批量操作
    - 持久化支持
    - 动态维度支持
    """

    def __init__(self, name: str = "default", dimension: int = 1536,
                 metric: str = "cosine"):
        self.name = name
        self.dimension = dimension
        self.metric = metric
        self._records: Dict[str, VectorRecord] = OrderedDict()
        self._namespace_index: Dict[str, List[str]] = {}  
        self._created_at = time.time()
        self._stats = {"total": 0, "queries": 0, "inserts": 0, "deletes": 0}

    def _validate_vector(self, vector: List[float]) -> bool:
        """验证向量维度"""
        if len(vector) != self.dimension:
            raise ValueError(
                f"向量维度 {len(vector)} 不匹配，期望 {self.dimension}"
            )
        return True

    def add(self, vector: List[float], metadata: Dict = None,
            record_id: str = None, namespace: str = "default") -> str:
        """添加向量记录"""
        self._validate_vector(vector)
        rid = record_id or f"vec_{uuid.uuid4().hex[:12]}"
        record = VectorRecord(
            id=rid, vector=vector,
            metadata=metadata or {},
        )
        self._records[rid] = record
        self._namespace_index.setdefault(namespace, []).append(rid)
        self._stats["total"] += 1
        self._stats["inserts"] += 1
        return rid

    def get(self, record_id: str) -> Optional[VectorRecord]:
        """获取单条记录"""
        return self._records.get(record_id)

    def delete(self, record_id: str) -> bool:
        """删除记录"""
        if record_id in self._records:
            del self._records[record_id]
            
            for ns, ids in self._namespace_index.items():
                if record_id in ids:
                    ids.remove(record_id)
            self._stats["total"] -= 1
            self._stats["deletes"] += 1
            return True
        return False

    def update(self, record_id: str, vector: List[float] = None,
               metadata: Dict = None) -> bool:
        """更新记录"""
        if record_id not in self._records:
            return False
        rec = self._records[record_id]
        if vector is not None:
            self._validate_vector(vector)
            rec.vector = vector
        if metadata is not None:
            rec.metadata.update(metadata)
        rec.updated_at = time.time()
        return True

    def search(self, query_vector: List[float], top_k: int = 10,
               namespace: str = None, filter_expr: Dict = None) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数
            namespace: 限制搜索的命名空间
            filter_expr: 元数据过滤条件

        Returns:
            [{id, score, metadata}, ...]
        """
        self._validate_vector(query_vector)
        self._stats["queries"] += 1

        
        if namespace and namespace in self._namespace_index:
            candidate_ids = self._namespace_index[namespace]
        else:
            candidate_ids = list(self._records.keys())

        
        candidates = [
            (rid, self._records[rid].vector)
            for rid in candidate_ids
            if rid in self._records
        ]

        if not candidates:
            return []

        
        if filter_expr:
            filtered = []
            for rid, vec in candidates:
                rec = self._records[rid]
                if self._match_filter(rec.metadata, filter_expr):
                    filtered.append((rid, vec))
            candidates = filtered

        
        if self.metric == "cosine":
            results = CosineSimilarity.batch_query(query_vector, candidates, top_k)
        elif self.metric == "euclidean":
            results = EuclideanDistance.batch_query(query_vector, candidates, top_k)
        else:
            
            results = CosineSimilarity.batch_query(query_vector, candidates, top_k)

        return [
            {
                "id": rid, "score": round(score, 6),
                "metadata": self._records[rid].metadata,
            }
            for rid, score in results
        ]

    def _match_filter(self, metadata: Dict, filter_expr: Dict) -> bool:
        """元数据过滤匹配"""
        for key, expected in filter_expr.items():
            actual = metadata.get(key)
            if isinstance(expected, dict):
                
                if "$gt" in expected and actual <= expected["$gt"]:
                    return False
                if "$lt" in expected and actual >= expected["lt"]:
                    return False
                if "$gte" in expected and actual < expected["$gte"]:
                    return False
                if "$lte" in expected and actual > expected["$lte"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def batch_add(self, vectors: List[List[float]],
                  metadatas: List[Dict] = None,
                  namespace: str = "default") -> List[str]:
        """批量添加"""
        ids = []
        metas = metadatas or [{}] * len(vectors)
        for vec, meta in zip(vectors, metas):
            rid = self.add(vec, metadata=meta, namespace=namespace)
            ids.append(rid)
        return ids

    def count(self, namespace: str = None) -> int:
        """统计记录数"""
        if namespace:
            return len(self._namespace_index.get(namespace, []))
        return len(self._records)

    def get_all(self, namespace: str = None) -> List[VectorRecord]:
        """获取所有记录"""
        if namespace:
            ids = self._namespace_index.get(namespace, [])
            return [self._records[i] for i in ids if i in self._records]
        return list(self._records.values())

    def clear(self, namespace: str = None):
        """清空存储"""
        if namespace:
            ids = self._namespace_index.pop(namespace, [])
            for rid in ids:
                self._records.pop(rid, None)
            self._stats["deletes"] += len(ids)
            self._stats["total"] -= len(ids)
        else:
            self._records.clear()
            self._namespace_index.clear()
            self._stats["total"] = 0
            self._stats["deletes"] += len(self._records)

    def save(self, filepath: str):
        """持久化到文件"""
        data = {
            "name": self.name,
            "dimension": self.dimension,
            "metric": self.metric,
            "records": {rid: rec.to_dict()
                       for rid, rec in self._records.items()},
            "namespace_index": self._namespace_index,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, filepath: str):
        """从文件加载"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.name = data["name"]
        self.dimension = data["dimension"]
        self.metric = data["metric"]
        self._namespace_index = data.get("namespace_index", {})
        for rid, rdata in data.get("records", {}).items():
            rec = VectorRecord(
                id=rdata["id"],
                vector=rdata["vector"],
                metadata=rdata.get("metadata", {}),
            )
            rec.created_at = rdata.get("created_at", time.time())
            rec.updated_at = rdata.get("updated_at", time.time())
            self._records[rid] = rec

    def get_stats(self) -> Dict:
        return {
            "name": self.name,
            "dimension": self.dimension,
            "metric": self.metric,
            **self._stats,
            "namespaces": list(self._namespace_index.keys()),
        }


class VectorStoreManager:
    """管理多个命名向量存储"""

    def __init__(self, base_dir: str = "./vector_stores"):
        self.base_dir = base_dir
        self._stores: Dict[str, VectorStore] = {}
        os.makedirs(base_dir, exist_ok=True)

    def create_store(self, name: str, dimension: int = 1536,
                     metric: str = "cosine") -> VectorStore:
        store = VectorStore(name=name, dimension=dimension, metric=metric)
        self._stores[name] = store
        return store

    def get_store(self, name: str) -> Optional[VectorStore]:
        return self._stores.get(name)

    def get_or_create(self, name: str, dimension: int = 1536,
                      metric: str = "cosine") -> VectorStore:
        if name not in self._stores:
            self._stores[name] = VectorStore(name=name, dimension=dimension,
                                             metric=metric)
        return self._stores[name]

    def list_stores(self) -> List[str]:
        return list(self._stores.keys())

    def delete_store(self, name: str) -> bool:
        if name in self._stores:
            del self._stores[name]
            return True
        return False

    def save_all(self):
        """保存所有存储"""
        for name, store in self._stores.items():
            path = os.path.join(self.base_dir, f"{name}.json")
            store.save(path)

    def load_all(self):
        """加载所有存储"""
        for fname in os.listdir(self.base_dir):
            if fname.endswith(".json"):
                name = fname[:-5]
                path = os.path.join(self.base_dir, fname)
                store = VectorStore(name=name)
                store.load(path)
                self._stores[name] = store

    def get_stats(self) -> Dict:
        return {
            "store_count": len(self._stores),
            "stores": {name: s.get_stats() for name, s in self._stores.items()},
        }