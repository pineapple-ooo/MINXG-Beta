"""

"""
from __future__ import annotations
import os
import time
import json
import asyncio
import sqlite3
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Any
from minxg.base import BaseWorker, tool


class PersistenceWorker(BaseWorker):
    worker_id = "persistence"
    version = "1.0.0"

    def __init__(self, db_path: str = None):
        """
        """
        self.db_path = db_path
        self._kv: Dict[str, Dict] = {}        
        self._index: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))  
        self._lock = threading.RLock()
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self._init_sqlite()
        self._start_time = time.time()
        self.tools: Dict = {}
        self._register_tools()

    def _init_sqlite(self):
        if not self.db_path:
            return
        try:
            self._sqlite_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    tags TEXT,
                    ttl_seconds INTEGER,
                    set_at REAL
                )
            """)
            self._sqlite_conn.commit()
            cur = self._sqlite_conn.execute("SELECT key, value, tags, ttl_seconds, set_at FROM kv_store")
            for key, value, tags_json, ttl, set_at in cur:
                tags = json.loads(tags_json) if tags_json else {}
                self._kv[key] = {"value": json.loads(value), "tags": tags,
                                 "ttl": ttl, "set_at": set_at}
                for tk, tv in tags.items():
                    self._index[tk][str(tv)].add(key)
        except Exception as e:
            self._sqlite_conn = None

    def _persist(self, key: str):
        if not self._sqlite_conn:
            return
        try:
            e = self._kv.get(key)
            if not e:
                self._sqlite_conn.execute("DELETE FROM kv_store WHERE key=?", (key,))
            else:
                self._sqlite_conn.execute(
                    "INSERT OR REPLACE INTO kv_store (key, value, tags, ttl_seconds, set_at) VALUES (?, ?, ?, ?, ?)",
                    (key, json.dumps(e["value"]), json.dumps(e["tags"]),
                     e["ttl"], e["set_at"]))
            self._sqlite_conn.commit()
        except Exception as ex:
            pass
    @tool(description="Write key=value with tags and ttl", category="kv")
    async def put(self, key: str, value, tags: dict = None,
                 ttl_seconds: int = 0) -> Dict:
        with self._lock:
            old = self._kv.get(key)
            if old:
                for tk, tv in old.get("tags", {}).items():
                    self._index[tk][str(tv)].discard(key)
            entry = {"value": value, "tags": tags or {},
                     "ttl": ttl_seconds, "set_at": time.time()}
            self._kv[key] = entry
            for tk, tv in (tags or {}).items():
                self._index[tk][str(tv)].add(key)
            self._persist(key)
        return {"key": key, "stored": True, "ttl": ttl_seconds}

    @tool(description="Read value by key, supports default", category="kv")
    async def get(self, key: str, default: Any = None) -> Dict:
        with self._lock:
            e = self._kv.get(key)
            if not e:
                return {"key": key, "found": False, "value": default}
            if e["ttl"] > 0 and (time.time() - e["set_at"]) > e["ttl"]:
                self._kv.pop(key, None)
                self._persist(key)
                return {"key": key, "found": False, "value": default, "expired": True}
            return {"key": key, "found": True, "value": e["value"],
                    "tags": e["tags"]}

    @tool(description="Delete key", category="kv")
    async def delete(self, key: str) -> Dict:
        with self._lock:
            existed = key in self._kv
            old = self._kv.pop(key, None)
            if old:
                for tk, tv in old.get("tags", {}).items():
                    self._index[tk][str(tv)].discard(key)
            self._persist(key)
        return {"key": key, "deleted": existed}

    @tool(description="Check if key exists", category="kv")
    async def contains(self, key: str) -> Dict:
        return {"key": key, "exists": key in self._kv}

    @tool(description="List all keys (optional tag filter)", category="kv")
    async def list_keys(self, tag_key: str = "", tag_value: str = "", limit: int = 1000) -> Dict:
        with self._lock:
            if tag_key and tag_value:
                keys = list(self._index.get(tag_key, {}).get(str(tag_value), set()))
            elif tag_key:
                keys = set()
                for v_set in self._index.get(tag_key, {}).values():
                    keys.update(v_set)
                keys = list(keys)
            else:
                keys = list(self._kv.keys())
        return {"count": len(keys), "keys": keys[:limit]}

    @tool(description="Query by tag (return key list)", category="index")
    async def query_by_tag(self, tag_key: str, tag_value: str = "") -> Dict:
        with self._lock:
            if tag_value:
                keys = list(self._index.get(tag_key, {}).get(str(tag_value), set()))
            else:
                keys = set()
                for v_set in self._index.get(tag_key, {}).values():
                    keys.update(v_set)
                keys = list(keys)
        results = []
        for k in keys:
            e = self._kv.get(k)
            if e:
                results.append({"key": k, "value": e["value"], "tags": e["tags"]})
        return {"tag": {tag_key: tag_value}, "count": len(results), "results": results}

    @tool(description="List all tag indexes", category="index")
    async def list_indexes(self) -> Dict:
        with self._lock:
            return {tk: {tv: len(ks) for tv, ks in tvs.items()}
                    for tk, tvs in self._index.items()}

    @tool(description="Batch put {key: value} dict", category="batch")
    async def mput(self, items: dict, tags: dict = None) -> Dict:
        count = 0
        for k, v in items.items():
            await self.put(k, v, tags=tags)
            count += 1
        return {"count": count}

    @tool(description="Batch get key list, return dict", category="batch")
    async def mget(self, keys: list) -> Dict:
        result = {}
        for k in keys:
            r = await self.get(k)
            if r["found"]:
                result[k] = r["value"]
        return {"count": len(result), "values": result}

    @tool(description="Set LRU cache with max_size", category="cache")
    async def cache_set(self, name: str, key: str, value, max_size: int = 1000) -> Dict:
        cache_attr = f"_cache_{name}"
        if not hasattr(self, cache_attr):
            setattr(self, cache_attr, {})
        cache: Dict[str, Dict] = getattr(self, cache_attr)
        cache[key] = {"value": value, "at": time.time()}
        if len(cache) > max_size:
            sorted_items = sorted(cache.items(), key=lambda x: x[1]["at"])
            for kk, _ in sorted_items[:len(cache) - max_size]:
                cache.pop(kk, None)
        return {"cache": name, "key": key, "size": len(cache)}

    @tool(description="Read LRU cache", category="cache")
    async def cache_get(self, name: str, key: str) -> Dict:
        cache_attr = f"_cache_{name}"
        cache: Dict = getattr(self, cache_attr, {})
        e = cache.get(key)
        if not e:
            return {"cache": name, "key": key, "found": False}
        return {"cache": name, "key": key, "found": True, "value": e["value"]}

    @tool(description="Overall statistics", category="info")
    async def stats(self) -> Dict:
        with self._lock:
            return {
                "total_keys": len(self._kv),
                "indexed_tags": sum(len(tvs) for tvs in self._index.values()),
                "uptime_sec": round(time.time() - self._start_time, 2),
                "sqlite_enabled": self._sqlite_conn is not None,
                "db_path": self.db_path,
            }


    @tool(description="Fuzzy search key names", category="search")
    async def search_keys(self, query: str, limit: int = 20) -> Dict:
        with self._lock:
            matches = []
            for key in self._kv:
                if query.lower() in key.lower():
                    matches.append(key)
            results = sorted(matches)[:limit]
            return {"query": query, "matches": results, "count": len(matches), "returned": len(results)}

    @tool(description="Fuzzy search value content", category="search")
    async def search_values(self, query: str, limit: int = 20) -> Dict:
        with self._lock:
            matches = []
            for key, val in list(self._kv.items()):
                if query.lower() in str(val).lower():
                    matches.append(key)
            results = sorted(matches)[:limit]
            return {"query": query, "matches": results, "count": len(matches), "returned": len(results)}

    @tool(description="Memory importance score (access/size/tags)", category="analyze")
    async def importance_score(self, key: str = None) -> Dict:
        with self._lock:
            if key:
                e = self._kv.get(key, {})
                if isinstance(e, dict):
                    tags = len(e.get("tags", []) if isinstance(e, dict) else [])
                    size = len(str(e))
                    score = min(100, tags * 10 + size // 100)
                    return {"key": key, "score": score, "tags": tags, "size": size}
                return {"key": key, "score": 0}
            
            scores = []
            for k in self._kv:
                e = self._kv[k]
                if isinstance(e, dict):
                    score = min(100, len(e.get("tags", []) if isinstance(e, dict) else []) * 10 + len(str(e)) // 100)
                else:
                    score = 10
                scores.append({"key": k, "score": score})
            scores.sort(key=lambda x: -x["score"])
            return {"total": len(scores), "top": scores[:20]}

    @tool(description="Clean up low-value memories", category="cleanup")
    async def prune_memory(self, score_threshold: int = 5) -> Dict:
        with self._lock:
            removed = []
            for key in list(self._kv.keys()):
                e = self._kv[key]
                if isinstance(e, dict):
                    score = len(e.get("tags", []) if isinstance(e, dict) else []) * 10 + len(str(e)) // 100
                else:
                    score = 10
                if score < score_threshold:
                    removed.append(key)
                    self._delete_from_index(key, e)
                    del self._kv[key]
            return {"removed": len(removed), "keys": removed, "remaining": len(self._kv)}

    @tool(description="Batch export memories to JSON", category="export")
    async def export_memory(self, output_path: str = None) -> Dict:
        with self._lock:
            data = {k: (v if isinstance(v, (dict, list, str, int, float, bool)) else str(v))
                    for k, v in self._kv.items()}
            if output_path:
                with open(output_path, "w") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return {"exported": len(data), "path": output_path, "size_bytes": os.path.getsize(output_path)}
            return {"exported": len(data), "data": data}

    @tool(description="Batch import memories from JSON file", category="import")
    async def import_memory(self, input_path: str, overwrite: bool = False) -> Dict:
        try:
            with open(input_path, "r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"error": "JSON top-level must be an object"}
            with self._lock:
                added = 0
                updated = 0
                for key, value in data.items():
                    if key in self._kv and not overwrite:
                        continue
                    was_new = key not in self._kv
                    if was_new:
                        added += 1
                    else:
                        updated += 1
                    self._kv[key] = value
                    self._add_to_index(key, value)
                return {"added": added, "updated": updated, "total_keys": len(self._kv)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Get memory statistics", category="info")
    async def memory_stats(self) -> Dict:
        with self._lock:
            sizes = [len(str(v)) for v in self._kv.values()]
            tags_count = sum(len(v.get("tags", [])) if isinstance(v, dict) else 0 for v in self._kv.values())
            total_bytes = sum(sizes)
            return {
                "total_keys": len(self._kv),
                "total_bytes": total_bytes,
                "avg_size": total_bytes // max(1, len(self._kv)),
                "max_size": max(sizes) if sizes else 0,
                "total_tags": tags_count,
                "sqlite_enabled": self._sqlite_conn is not None,
            }
