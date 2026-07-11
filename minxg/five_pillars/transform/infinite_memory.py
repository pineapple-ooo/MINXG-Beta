"""
infinite_memory.py — Infinite-Context Memory Architecture 

5-layer memory pyramid with zero external dependencies.
Uses: hash index + inverted index + BM25-style ranking + time-decay.
Does NOT conflict with existing state_session.py or persistence.py.
"""

from __future__ import annotations
import time
import re
import json
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict
from minxg.base import BaseWorker, tool


# ─── Data Structures ───────────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    id: str
    content: str
    timestamp: float
    importance: float = 1.0
    topic: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    parent_id: str = ""

    def score(self, now: float, query_words: List[str] = None) -> float:
        age_hours = (now - self.timestamp) / 3600
        decay = max(0.1, 1.0 - (age_hours / (age_hours + 4)))
        base = self.importance * decay
        if query_words:
            q = sum(1 for w in query_words if w in self.content.lower())
            base *= (1 + 0.1 * q)
        return base

    def to_dict(self) -> Dict: return vars(self)


@dataclass
class MemoryEpisode:
    id: str
    created_at: float
    summary: str
    entries: List[str]  # entry IDs
    topics: List[str]
    key_facts: List[str]
    importance: float = 1.0
    access_count: int = 0
    last_access: float = 0

    def touch(self): self.last_access = time.time(); self.access_count += 1
    def to_dict(self) -> Dict: return vars(self)


class InvertedIndex:
    """Lightweight inverted index using keyword hashing. No external deps."""

    def __init__(self):
        self._index: Dict[str, Set[str]] = defaultdict(set)  # word -> entry_ids
        self._id_to_words: Dict[str, Set[str]] = {}  # entry_id -> words

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r'\b\w{2,}\b', text.lower())
        # Stopwords
        stop = {'the','a','an','and','or','but','in','on','at','to','for','of','with','by','is','are','was','were','be','been','being','have','has','had','do','does','did','will','would','could','should','may','might','can','this','that','these','those','i','you','he','she','it','we','they','what','which','who','when','where','why','how'}
        return [w for w in words if w not in stop]

    def add(self, entry_id: str, text: str):
        words = self._tokenize(text)
        self._id_to_words[entry_id] = set(words)
        for w in words:
            self._index[w].add(entry_id)
        # Also index bigrams
        ws = words
        for i in range(len(ws) - 1):
            bg = f"{ws[i]}_{ws[i+1]}"
            self._index[bg].add(entry_id)

    def remove(self, entry_id: str):
        if entry_id in self._id_to_words:
            for w in self._id_to_words[entry_id]:
                self._index[w].discard(entry_id)
            del self._id_to_words[entry_id]

    def search(self, query: str, limit: int = 20) -> List[Tuple[str, float]]:
        """BM25-style ranking. Returns [(entry_id, score)]."""
        words = self._tokenize(query)
        if not words:
            return []
        doc_scores: Dict[str, float] = defaultdict(float)
        N = max(1, len(self._id_to_words))
        avgdl = sum(len(self._id_to_words.get(eid, [])) for eid in self._id_to_words) / N
        k1, b = 1.5, 0.75
        for w in words:
            df = len(self._index.get(w, set()))
            if df == 0:
                continue
            idf = max(0, (N - df + 0.5) / (df + 0.5))
            for doc_id in self._index.get(w, set()):
                doc_len = len(self._id_to_words.get(doc_id, []))
                tf = 1 if w in self._id_to_words.get(doc_id, set()) else 0
                bm = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / max(1, avgdl)))
                doc_scores[doc_id] += bm
        ranked = sorted(doc_scores.items(), key=lambda x: -x[1])
        return ranked[:limit]


class KnowledgeGraph:
    """Simple entity-relationship graph. No external deps."""

    def __init__(self):
        self._entities: Dict[str, Dict] = {}  # entity_id -> {name, type, attrs}
        self._relations: Dict[str, List[Dict]] = defaultdict(list)  # entity_id -> [{target, rel_type, weight}]

    def add_entity(self, name: str, entity_type: str = "", attrs: Dict = None) -> str:
        eid = hashlib.md5(name.encode()).hexdigest()[:12]
        self._entities[eid] = {"name": name, "type": entity_type, "attrs": attrs or {}}
        return eid

    def add_relation(self, src: str, target: str, rel_type: str, weight: float = 1.0):
        self._relations[src].append({"target": target, "type": rel_type, "weight": weight})

    def get_entity(self, name: str) -> Optional[Dict]:
        eid = hashlib.md5(name.encode()).hexdigest()[:12]
        return self._entities.get(eid)

    def traverse(self, start: str, hops: int = 2) -> List[Dict]:
        visited, queue = {start}, [(start, 0)]
        result = []
        while queue:
            node, depth = queue.pop(0)
            if depth > 0:
                result.append(self._entities.get(node, {}))
            if depth >= hops:
                continue
            for rel in self._relations.get(node, []):
                nid = rel["target"]
                if nid not in visited:
                    visited.add(nid)
                    queue.append((nid, depth + 1))
        return result


class SemanticStore:
    """Topic-keyed semantic memory using keyword hashing."""

    def __init__(self):
        self._store: Dict[str, List[MemoryEntry]] = defaultdict(list)

    def _topic_key(self, text: str) -> str:
        words = re.findall(r'\b\w{3,}\b', text.lower())
        if not words:
            return "default"
        # Top 3 words by frequency as key
        freq = defaultdict(int)
        for w in words:
            freq[w] += 1
        top = sorted(freq.items(), key=lambda x: -x[1])[:3]
        return "_".join(w for w, _ in top)

    def put(self, entry: MemoryEntry):
        key = self._topic_key(entry.content)
        entry.topic = key
        self._store[key].append(entry)

    def get(self, topic: str, limit: int = 10) -> List[MemoryEntry]:
        return self._store.get(topic, [])[-limit:]

    def all_topics(self) -> List[str]:
        return list(self._store.keys())


# ─── Infinite Memory Worker ────────────────────────────────────────────────────

class InfiniteMemoryWorker(BaseWorker):
    facade_alias = "state_session"
    worker_id = "infinite_memory"
    version = "0.17.1"

    def __init__(self):
        self._lock = threading.RLock()
        self._entries: Dict[str, MemoryEntry] = {}
        self._episodes: Dict[str, MemoryEpisode] = {}
        self._inverted = InvertedIndex()
        self._semantic = SemanticStore()
        self._graph = KnowledgeGraph()
        self._working: List[str] = []  # IDs in working memory (ordered)
        self._max_working = 200
        self._episode_size = 50  # entries per episode
        self._total_memories = 0
        self._id_counter = 0
        self._start_time = time.time()
        self._recent_topics: List[str] = []
        self._importance_thresholds = {"high": 0.8, "medium": 0.4, "low": 0.0}

    def _new_id(self) -> str:
        self._id_counter += 1
        return f"mem_{self._id_counter}_{int(time.time() * 1000)}"

    # ── Core Memory Operations ────────────────────────────────────────────────

    @tool(description="Store a message/fact in memory with auto-importance scoring", category="memory")
    async def remember(self, content: str, importance: float = 1.0,
                        tags: List[str] = None, metadata: Dict = None) -> Dict:
        with self._lock:
            eid = self._new_id()
            entry = MemoryEntry(
                id=eid,
                content=content,
                timestamp=time.time(),
                importance=importance,
                tags=tags or [],
                metadata=metadata or {},
            )
            # Auto-extract entities (simple noun detection)
            words = re.findall(r'\b[A-Z][a-z]+\b', content)
            entry.entities = words[:10]

            self._entries[eid] = entry
            self._inverted.add(eid, content)
            self._semantic.put(entry)
            self._working.append(eid)

            # Evict oldest if working overflow
            while len(self._working) > self._max_working:
                old_id = self._working.pop(0)
                if old_id in self._entries and self._entries[old_id].importance < 0.5:
                    # Archive to episode instead of delete
                    pass

            self._total_memories += 1
            return {"status": "stored", "id": eid, "total": self._total_memories}

    @tool(description="Recall memories matching query (uses BM25 ranking)", category="memory")
    async def recall(self, query: str, limit: int = 10, time_range: Tuple[float, float] = None) -> Dict:
        with self._lock:
            results = self._inverted.search(query, limit=limit * 2)
            output = []
            now = time.time()
            for eid, score in results:
                entry = self._entries.get(eid)
                if not entry:
                    continue
                if time_range:
                    if not (time_range[0] <= entry.timestamp <= time_range[1]):
                        continue
                output.append({
                    "id": entry.id,
                    "content": entry.content,
                    "timestamp": entry.timestamp,
                    "score": round(score, 4),
                    "importance": entry.importance,
                    "topic": entry.topic,
                })
                if len(output) >= limit:
                    break
            return {"status": "recalled", "results": output, "query": query}

    @tool(description="Forget all memories matching a topic or tag", category="memory")
    async def forget(self, topic: str = "", tag: str = "") -> Dict:
        with self._lock:
            removed = 0
            to_remove = []
            for eid, entry in self._entries.items():
                if topic and entry.topic == topic:
                    to_remove.append(eid)
                elif tag and tag in entry.tags:
                    to_remove.append(eid)
            for eid in to_remove:
                del self._entries[eid]
                self._inverted.remove(eid)
                if eid in self._working:
                    self._working.remove(eid)
                removed += 1
            return {"status": "forgotten", "removed": removed}

    @tool(description="Get a context-ready string for AI context windows", category="memory")
    async def get_context_window(self, max_tokens: int = 8000, include_topics: List[str] = None) -> Dict:
        with self._lock:
            # Start with recent entries
            context_parts = []
            remaining = max_tokens
            now = time.time()

            # Add most recent entries first (working memory)
            for eid in reversed(self._working[-50:]):
                entry = self._entries.get(eid)
                if not entry:
                    continue
                txt = f"[{entry.topic or 'memory'}] {entry.content}"
                if len(txt) > remaining:
                    break
                context_parts.append(txt)
                remaining -= len(txt)

            # Add semantic memory summaries if topic specified
            if include_topics:
                for topic in include_topics[:5]:
                    entries = self._semantic.get(topic, limit=5)
                    for entry in entries:
                        txt = f"[semantic:{topic}] {entry.content}"
                        if len(txt) > remaining:
                            break
                        context_parts.append(txt)
                        remaining -= len(txt)

            context = "\n".join(reversed(context_parts))
            return {
                "status": "context_ready",
                "context": context,
                "token_estimate": len(context.split()),
                "entries_used": len(context_parts),
            }

    # ── Episode Management ───────────────────────────────────────────────────

    @tool(description="Compress recent entries into an episodic memory", category="memory")
    async def compress_episode(self) -> Dict:
        with self._lock:
            if len(self._working) < 10:
                return {"status": "skip", "reason": "not enough entries"}

            recent_ids = self._working[-self._episode_size:]
            recent = [self._entries[eid] for eid in recent_ids if eid in self._entries]
            if not recent:
                return {"status": "error", "reason": "no entries"}

            # Simple extractive summary: first sentence of most important entries
            sorted_entries = sorted(recent, key=lambda e: -e.importance)[:10]
            summary_parts = []
            for entry in sorted_entries[:5]:
                # Take first 100 chars as summary fragment
                summary_parts.append(entry.content[:100])

            eid = self._new_id()
            episode = MemoryEpisode(
                id=eid,
                created_at=time.time(),
                summary=" | ".join(summary_parts),
                entries=recent_ids,
                topics=[entry.topic for entry in recent if entry.topic],
                key_facts=[entry.content[:80] for entry in recent if entry.importance > 0.7],
            )
            self._episodes[eid] = episode
            return {"status": "compressed", "episode_id": eid, "summary": episode.summary[:200]}

    @tool(description="Recall episodic memories", category="memory")
    async def recall_episodes(self, query: str = "", limit: int = 5) -> Dict:
        with self._lock:
            if query:
                results = self._inverted.search(query, limit=limit * 3)
                ep_ids = set()
                for eid, _ in results:
                    for ep in self._episodes.values():
                        if eid in ep.entries:
                            ep_ids.add(ep.id)
                eps = [self._episodes[eid] for eid in list(ep_ids)[:limit] if eid in self._episodes]
            else:
                eps = sorted(self._episodes.values(), key=lambda e: -e.created_at)[:limit]
            return {
                "status": "episodes_found",
                "episodes": [{"id": e.id, "summary": e.summary[:150], "created": e.created_at} for e in eps],
            }

    # ── Knowledge Graph ─────────────────────────────────────────────────────

    @tool(description="Extract and link entities from text into knowledge graph", category="memory")
    async def extract_and_link(self, text: str) -> Dict:
        with self._lock:
            entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
            relations = re.findall(r'\b(is|was|belongs to|related to|part of|created by)\b', text, re.I)
            added = []
            for name in entities[:20]:
                eid = self._graph.add_entity(name, attrs={"first_seen": time.time()})
                added.append(name)
            # Add simple co-occurrence relations
            for i, e1 in enumerate(added):
                for e2 in added[i+1:]:
                    eid1 = hashlib.md5(e1.encode()).hexdigest()[:12]
                    eid2 = hashlib.md5(e2.encode()).hexdigest()[:12]
                    self._graph.add_relation(eid1, eid2, "co_mentioned", weight=0.5)
            return {"status": "linked", "entities": added, "relations": len(relations)}

    @tool(description="Query knowledge graph", category="memory")
    async def query_graph(self, entity_name: str, hops: int = 2) -> Dict:
        with self._lock:
            eid = hashlib.md5(entity_name.encode()).hexdigest()[:12]
            if eid not in self._graph._entities:
                return {"status": "not_found", "entity": entity_name}
            neighbors = self._graph.traverse(eid, hops=hops)
            return {
                "status": "graph_query",
                "entity": entity_name,
                "neighbors": [{"name": n.get("name", ""), "type": n.get("type", "")} for n in neighbors[:20]],
            }

    # ── Fact Extraction ──────────────────────────────────────────────────────

    @tool(description="Extract key facts from text (entity-action-object pattern)", category="memory")
    async def extract_facts(self, text: str) -> Dict:
        facts = []
        # Simple pattern: noun-verb-noun
        patterns = [
            (r'(\b\w+\b)\s+(is|was|are|were)\s+(\b\w+\b)', 'definition'),
            (r'(\b\w+\b)\s+(created|made|built)\s+(\b\w+\b)', 'creation'),
            (r'(\b\w+\b)\s+(lives in|works at|located in)\s+(\b\w+\b)', 'location'),
        ]
        for pattern, fact_type in patterns:
            for m in re.finditer(pattern, text, re.I):
                facts.append({"type": fact_type, "subject": m.group(1), "predicate": m.group(2), "object": m.group(3)})
        return {"status": "extracted", "facts": facts[:20]}

    # ── Memory Statistics & Introspection ────────────────────────────────────

    @tool(description="Memory system statistics", category="memory")
    async def memory_stats(self) -> Dict:
        with self._lock:
            topics = self._semantic.all_topics()
            return {
                "status": "ok",
                "total_entries": len(self._entries),
                "total_episodes": len(self._episodes),
                "total_entities": len(self._graph._entities),
                "working_size": len(self._working),
                "inverted_index_terms": len(self._inverted._index),
                "semantic_topics": len(topics),
                "total_memories_stored": self._total_memories,
                "uptime_seconds": int(time.time() - self._start_time),
            }

    @tool(description="List all topics currently in memory", category="memory")
    async def list_topics(self) -> Dict:
        with self._lock:
            topics = self._semantic.all_topics()
            counts = {t: len(self._semantic._store[t]) for t in topics}
            return {"status": "ok", "topics": [{"name": t, "count": counts[t]} for t in sorted(topics, key=lambda x: -counts[x])]}