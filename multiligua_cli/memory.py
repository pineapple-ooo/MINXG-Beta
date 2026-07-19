"""
MINXG Memory System — Dual-Layer Architecture v3.0 (Entropic)
================================================================================

Layer 1 (Working Memory): ephemeral session state — tool trace, active files,
    errors, constraints.  ~300 tokens injected each turn.

Layer 2 (Entropic Evolution): information-theoretic self-evolution engine.
    Uses Jensen-Shannon divergence (not regex), causal PC algorithm (not
    correlation), fractal SimHash compression (not flat storage), and
    AES-256-GCM encrypted persistence (not plaintext SQLite).

BACKWARD COMPATIBLE: all existing call sites (get_evolution_engine,
learn_from_exchange, get_memory_context) continue to work unchanged.

Config (config.yaml):
  memory:
    enabled: true
    auto_learn: true
    decay_days: 90
    backend: "entropic"       # new: "entropic" or "legacy"
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple



MINXG_HOME = Path.home() / ".minxg"
MEMORY_DIR = MINXG_HOME / "memory"
MEMORY_DB = MEMORY_DIR / "memory.db"


def _ensure_dirs():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)






class MemoryStore:
    """Persistent key-value store for user preferences, facts, and learned
    patterns.  Backed by SQLite with weight-based decay.  Thread-safe.

    NOTE: In the new entropic architecture, this is a compatibility layer.
    The primary storage is now the Secure Encrypted Store (secure_store.py).
    """

    def __init__(self, db_path: str = None):
        _ensure_dirs()
        self.db_path = db_path or str(MEMORY_DB)
        self._lock = threading.Lock()
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    key         TEXT NOT NULL UNIQUE,
                    value       TEXT NOT NULL,
                    category    TEXT NOT NULL DEFAULT 'user_pref',
                    tags        TEXT DEFAULT '',
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL,
                    accessed_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    weight      REAL DEFAULT 1.0,
                    pinned      INTEGER DEFAULT 0
            )""")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_accessed ON memories(accessed_at)")
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, key: str, value: Any, category: str = "user_pref",
             tags: List[str] = None, pinned: bool = False) -> bool:
        now = time.time()
        value_str = json.dumps(value, ensure_ascii=False) if not isinstance(
            value, str) else value
        tags_str = ",".join(tags) if tags else ""
        with self._lock, self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO memories (key, value, category, tags,
                        created_at, updated_at, accessed_at, weight, pinned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        category = excluded.category,
                        tags = excluded.tags,
                        updated_at = excluded.updated_at,
                        accessed_at = excluded.accessed_at,
                        access_count = access_count + 1
                """, (key, value_str, category, tags_str, now, now, now, int(pinned)))
                conn.commit()
                return True
            except Exception:
                return False

    def get(self, key: str) -> Optional[dict]:
        with self._lock, self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE key = ?", (key,)
            ).fetchone()
            if row:
                conn.execute("""
                    UPDATE memories
                    SET accessed_at = ?, access_count = access_count + 1
                    WHERE key = ?
                """, (time.time(), key))
                conn.commit()
                return self._row_to_dict(row)
        return None

    def delete(self, key: str) -> bool:
        with self._lock, self._get_conn() as conn:
            conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.commit()
            return True

    def list_all(self, category: str = None) -> List[dict]:
        with self._get_conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE category = ? ORDER BY weight DESC",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories ORDER BY weight DESC"
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by(self, category: str, limit: int = 20) -> List[dict]:
        return self.list_all(category=category)[:limit]

    def count(self, category: str = None) -> int:
        with self._get_conn() as conn:
            if category:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM memories WHERE category = ?",
                    (category,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()
        return row["cnt"] if row else 0

    def search(self, query: str, limit: int = 10) -> List[dict]:
        with self._get_conn() as conn:
            keywords = query.strip().lower().split()
            conditions = []
            params = []
            for kw in keywords:
                pattern = f"%{kw}%"
                conditions.append(
                    "(key LIKE ? OR value LIKE ? OR tags LIKE ?)")
                params.extend([pattern, pattern, pattern])
            where = " OR ".join(conditions)
            sql = f"""
                SELECT * FROM memories
                WHERE {where}
                ORDER BY weight DESC, accessed_at DESC
                LIMIT ?
            """
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search_by_tag(self, tag: str) -> List[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE tags LIKE ? ORDER BY weight DESC",
                (f"%{tag}%",)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def apply_decay(self, decay_days: int = 90):
        cutoff = time.time() - (decay_days * 86400)
        with self._lock, self._get_conn() as conn:
            conn.execute("""
                UPDATE memories
                SET weight = 0.3
                WHERE accessed_at < ? AND pinned = 0 AND weight > 0.3
            """, (cutoff,))
            conn.execute("""
                UPDATE memories
                SET weight = 0.1
                WHERE accessed_at < ? AND pinned = 0 AND weight > 0.1
            """, (time.time() - (decay_days * 2 * 86400),))
            conn.commit()

    def prune_low_weight(self, threshold: float = 0.05, max_entries: int = 1000):
        total = self.count()
        if total <= max_entries:
            return
        to_remove = total - max_entries
        with self._lock, self._get_conn() as conn:
            conn.execute("""
                DELETE FROM memories WHERE id IN (
                    SELECT id FROM memories
                    WHERE pinned = 0
                    ORDER BY weight ASC, accessed_at ASC
                    LIMIT ?
                )
            """, (to_remove,))
            conn.commit()

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "key": row["key"],
            "value": row["value"],
            "category": row["category"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "accessed_at": row["accessed_at"],
            "access_count": row["access_count"],
            "weight": row["weight"],
            "pinned": bool(row["pinned"]),
        }

    def get_context_for_prompt(self, max_items: int = 5) -> str:
        items = self.list_all()
        if not items:
            return ""
        top = sorted(items, key=lambda x: x["weight"], reverse=True)[:max_items]
        lines = []
        for item in top:
            val = item["value"]
            if isinstance(val, str) and len(val) > 200:
                val = val[:200] + "..."
            lines.append(f"  - [{item['category']}] {item['key']}: {val}")
        return "\n".join(lines)






_PREFERENCE_PATTERNS = [
    (r"(?:用中文|用英文|说中文|说英文|speak|write|respond|reply)\s+(?:in\s+)?(中文|英文|English|Chinese)",
     "language",
     lambda m: {"key": "language_pref", "value": m.group(1).strip(),
                "tags": ["language"]}),
    (r"(?:我是|我的名字是|my name is|I am|I'm)\s+(.{2,40})",
     "identity",
     lambda m: {"key": "user_name", "value": m.group(1).strip(),
                "tags": ["identity"]}),
    (r"(?:项目|project|codebase)(?:在|at|in)\s+(/\S+)",
     "project",
     lambda m: {"key": "project_path", "value": m.group(1).strip(),
                "tags": ["path", "project"]}),
    (r"(?:不要|别|禁止|不要用|don't|never|stop|no)\s+(.{2,80})",
     "negative",
     lambda m: {"key": "negative_pref", "value": m.group(1).strip(),
                "tags": ["negative", "correction"]}),
    (r"(?:回答|输出|回复)(?:要|请|尽量)\s*(简洁|详细|简短|具体|verbose|concise|brief|detailed)",
     "style",
     lambda m: {"key": "style_pref", "value": m.group(1).strip(),
                "tags": ["style"]}),
    (r"(?:不要|别)(?:用|写)(?:markdown|Markdown|代码块|表格|emoji|注水)",
     "format_constraint",
     lambda m: {"key": "format_constraint", "value": m.group(0).strip(),
                "tags": ["format", "negative"]}),
]


def extract_preferences(text: str) -> List[dict]:
    results = []
    seen_keys = set()
    for pattern, category, extractor in _PREFERENCE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        try:
            entry = extractor(match)
        except Exception:
            continue
        if entry["key"] not in seen_keys:
            seen_keys.add(entry["key"])
            results.append(entry)
    return results






class EvolutionEngine:
    """Self-learning engine — now powered by the Entropic Evolution Engine.

    This facade maintains the exact API contract expected by tui_chat.py
    and other callers, while routing to the new entropic backend.

    API:
      learn_from_exchange(user_msg, assistant_msg, tool_calls) -> int
      get_memory_context(max_items) -> str
      learn_from_user_message(message) -> int
      learn_from_tool_call(tool_name)
      get_tool_stats() -> dict
      get_stats() -> dict
      .store -> MemoryStore instance
    """

    def __init__(self, store: MemoryStore = None, backend: str = "entropic"):
        self.store = store or MemoryStore()
        self._conversation_count = 0
        self._tool_usage: Dict[str, int] = {}
        self._backend_name = backend

        
        self._entropic_engine = None
        if backend == "entropic":
            try:
                from src.ai.memory.entropic_evolution import get_entropic_engine
                self._entropic_engine = get_entropic_engine()
            except ImportError:
                
                self._backend_name = "legacy"

    @property
    def backend(self) -> str:
        return self._backend_name

    

    def learn_from_exchange(self, user_msg: str, assistant_msg: str = "",
                            tool_calls: List[str] = None) -> int:
        """Process one conversational exchange. Returns number of items learned.

        Routes to entropic engine if available, falls back to legacy.
        """
        self._conversation_count += 1

        if self._entropic_engine:
            result = self._entropic_engine.learn_from_exchange(
                user_msg, assistant_msg, tool_calls or [])
            return result["behaviors_learned"]

        
        user_learned = self.learn_from_user_message(user_msg)
        if tool_calls:
            for t in tool_calls:
                self.learn_from_tool_call(t)
        if self._conversation_count % 50 == 0:
            self.store.apply_decay()
        return user_learned

    def learn_from_user_message(self, message: str) -> int:
        """Learn preferences from a single user message."""
        if self._entropic_engine:
            return self._entropic_engine.learn_from_user_message(message)

        
        extracted = extract_preferences(message)
        saved = 0
        for entry in extracted:
            key = entry["key"]
            existing = self.store.get(key)
            self.store.save(
                key, entry["value"],
                category=entry.get("category", "learned_pattern"),
                tags=entry.get("tags", []),
                pinned=existing.get("pinned", False) if existing else False,
            )
            saved += 1
        return saved

    def learn_from_tool_call(self, tool_name: str):
        """Record a tool call."""
        self._tool_usage[tool_name] = self._tool_usage.get(tool_name, 0) + 1
        if self._entropic_engine:
            self._entropic_engine.learn_from_tool_call(tool_name)

        if self._tool_usage[tool_name] >= 10:
            self.store.save(
                f"frequent_tool_{tool_name}",
                {"tool": tool_name, "count": self._tool_usage[tool_name]},
                category="learned_pattern",
                tags=["tool", "frequent"],
            )

    

    def get_memory_context(self, max_items: int = 5) -> str:
        """Return dual-layer memory context for prompt injection.

        Layer 1 (Working Memory): what just happened — ~300 tokens.
        Layer 2 (Entropic/DB Memory): persistent preferences — ~200 tokens.
        """
        if self._entropic_engine:
            
            return self._entropic_engine.get_memory_context(max_items)

        
        layers = []
        try:
            from src.ai.memory.working_memory import get_working_memory
            wm = get_working_memory()
            wm_inject = wm.inject()
            if wm_inject:
                layers.append(wm_inject)
        except ImportError:
            pass

        fact = self.store.get_context_for_prompt(max_items)
        if fact:
            layers.append(
                "[FACT MEMORY — persistent preferences and facts]\n" + fact)

        return "\n\n".join(layers) if layers else ""

    

    def get_tool_stats(self) -> Dict[str, int]:
        if self._entropic_engine:
            return self._entropic_engine.get_tool_stats()
        return dict(self._tool_usage)

    def get_stats(self) -> dict:
        if self._entropic_engine:
            stats = self._entropic_engine.get_stats()
            stats["backend"] = self._backend_name
            return stats

        return {
            "backend": "legacy",
            "total_memories": self.store.count(),
            "conversations_learned": self._conversation_count,
            "tool_usage": self._tool_usage,
            "categories": {
                c: self.store.count(c)
                for c in ["user_pref", "learned_pattern", "environment",
                          "correction", "pinned"]
            },
        }






_engine: Optional[EvolutionEngine] = None


def get_evolution_engine() -> EvolutionEngine:
    """Get or create the global EvolutionEngine singleton.

    Uses entropic backend by default, falls back to legacy if unavailable.
    """
    global _engine
    if _engine is None:
        _engine = EvolutionEngine(backend="entropic")
    return _engine


def get_memory_store() -> MemoryStore:
    """Get the memory store (backward compat)."""
    return get_evolution_engine().store


def get_entropic_engine():
    """Direct access to the entropic engine (for advanced use)."""
    eng = get_evolution_engine()
    return eng._entropic_engine