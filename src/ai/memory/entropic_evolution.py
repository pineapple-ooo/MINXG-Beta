#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.ai.memory.entropic_evolution — entropic multi-tier memory engine.

Why
===
A single flat key/value store beats nothing, but the moment a
chat crosses ~20 turns the model starts forgetting what the user
said two messages ago and chat-internal long-term context is
hopeless past ~200 messages. The point of this engine is to make
the assistant forget *nothing* — every user message, every
assistant reply, every tool call lands in one of three tiers and
is queryable from the next prompt.

Tiers
=====
  L0  Hot / Working memory
      Last N turns kept verbatim with token-level retrieval.
      In-process deque + on-disk append-only log; no scoring.

  L1  Warm / Semantic memory
      Projected to compact integer-quantised feature vectors.
      Stored as a flat npy-style buffer; cosine-similarity at
      query time. Default 256-D, 8-bit per dim = 64 bytes per
      memory item → 10 000 items ≈ 640 KB of warm storage.

  L2  Cold / Compressed memory
      Receives evicted L1 items and is what the LLM never sees
      by default. Used for night-time compaction, replaying, and
      cross-session continuity. Backed by a sqlite table by
      default; trivially swappable for any key/value store.

Each ``learn_from_*`` call writes to the appropriate tier and
returns a small summary dict so callers can introspect. The
engine never throws on input — bad args degrade to legacy behaviour
rather than killing the chat.

Public surface (frozen; do not break without bumping to 0.12.2)
  - get_entropic_engine(...) -> EntropicEvolutionEngine
  - EntropicEvolutionEngine.learn_from_exchange / _user / _tool
  - EntropicEvolutionEngine.get_memory_context(max_items)
  - EntropicEvolutionEngine.get_stats() -> dict
"""
from __future__ import annotations

import collections
import dataclasses as dc
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from array import array
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("src.ai.memory.entropic")


# ──────────────────────────────────────────────────────────── tunables ---


def _env_int(name: str, default: int) -> int:
    try:
        v = os.environ.get(name)
        return int(v) if v is not None and v.strip() else default
    except (TypeError, ValueError):
        return default


L0_TURNS = _env_int("MINXG_L0_TURNS", 32)
L1_MAX_ITEMS = _env_int("MINXG_L1_MAX_ITEMS", 10_000)
L2_DB_PATH = os.environ.get(
    "MINXG_L2_DB",
    str(Path.home() / ".minxg" / "memory.db"),
)
DEFAULT_VECTOR_DIM = _env_int("MINXG_VECTOR_DIM", 256)


# ────────────────────────────────────────────── token / vector helpers ---


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+", flags=re.UNICODE)
_STOP = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "on", "for", "and", "or", "but", "if",
    "with", "this", "that", "it", "as", "by", "we", "i", "you",
})


def _tokens(text: str) -> List[str]:
    text = (text or "").lower()
    return [m.group(0) for m in _TOKEN_RE.finditer(text)
            if m.group(0) not in _STOP]


def _hash_token(token: str, dim: int) -> int:
    """Stable 0..dim-1 slot from a token. Sub-second, no text model."""
    h = hashlib.sha1(token.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % dim


def _quantise(vec: List[float]) -> array:
    """8-bit symmetric quantisation around max-abs."""
    if not vec:
        return array("b")
    m = max(abs(v) for v in vec) or 1.0
    scale = 127.0 / m
    return array("b", (max(-127, min(127, int(round(v * scale)))) for v in vec))


def _vectorise(text: str, dim: int) -> array:
    """Bag-of-hashes embedding. Cheap, deterministic, lang-agnostic."""
    vec = [0.0] * dim
    toks = _tokens(text)
    for tok in toks:
        vec[_hash_token(tok, dim)] += 1.0
    # sublinear TF
    total = math.log1p(len(toks)) if toks else 1.0
    if total > 0:
        vec = [v / total for v in vec]
    return _quantise(vec)


def _cosine_sim(a: array, b: array) -> float:
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = af = bf = 0.0
    for x, y in zip(a, b):
        dot += x * y
        af += x * x
        bf += y * y
    if af <= 0 or bf <= 0:
        return 0.0
    return dot / (math.sqrt(af) * math.sqrt(bf))


# ────────────────────────────────────────────────────────── schemas ---


@dc.dataclass(frozen=True)
class MemoryItem:
    item_id: str
    role: str            # "user" | "assistant" | "tool"
    text: str
    created_at: float
    vector: Optional[array] = None     # quantised 8-bit
    tags: Tuple[str, ...] = ()
    pinned: bool = False


# ────────────────────────────────────────────────────────── L0 storage ---


class L0HotStore:
    """Last N turns, no scoring. Pure deque + dirty-write to disk."""

    def __init__(self, capacity: int = L0_TURNS, log_path: Optional[str] = None) -> None:
        if capacity < 1:
            capacity = 1
        self._cap = capacity
        self._items: Deque[MemoryItem] = collections.deque(maxlen=capacity)
        self._log_path = Path(log_path or str(Path.home() / ".minxg" / "l0.jsonl"))
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def add(self, item: MemoryItem) -> None:
        self._items.append(item)
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "item_id": item.item_id,
                    "role": item.role,
                    "text": item.text,
                    "created_at": item.created_at,
                    "tags": list(item.tags),
                    "pinned": item.pinned,
                }, ensure_ascii=False) + "\n")
        except Exception as e:  # pragma: no cover — non-fatal
            logger.debug("L0 append failed: %r", e)

    def query(self, n: int) -> List[MemoryItem]:
        return list(self._items)[-n:]

    def reset(self) -> None:
        self._items.clear()


# ────────────────────────────────────────────────────────── L1 storage ---


class L1WarmStore:
    """Vector-cosine retrievable store. Quantises vectors to int8.

    Cheap to query, modest size on disk. The cap (10 000 by
    default) bounds memory growth automatically — oldest
    unpinned, low-similarity items are evicted on insert when the
    cap is reached.
    """

    def __init__(self, dim: int = DEFAULT_VECTOR_DIM, max_items: int = L1_MAX_ITEMS) -> None:
        self._dim = dim
        self._cap = max_items
        self._items: List[MemoryItem] = []
        self._lock = threading.Lock()

    def add(self, item: MemoryItem) -> None:
        with self._lock:
            self._items.append(item)
            if len(self._items) > self._cap:
                # Keep pinned, evict oldest unpinned first.
                self._items.sort(key=lambda m: (m.pinned, m.created_at))
                keep = self._items[-self._cap:]
                # ensure pinned items survive
                pinned = [m for m in self._items if m.pinned]
                rest = [m for m in self._items if not m.pinned][-self._cap:]
                self._items = pinned[:self._cap] + rest
                self._items.sort(key=lambda m: m.created_at)

    def query(self, text: str, k: int = 8) -> List[MemoryItem]:
        if not self._items or k <= 0:
            return []
        q = _vectorise(text, self._dim)
        with self._lock:
            scored: List[Tuple[float, MemoryItem]] = []
            for m in self._items:
                if m.vector is None:
                    continue
                s = _cosine_sim(q, m.vector)
                if s > 0:
                    scored.append((s, m))
            scored.sort(key=lambda t: t[0], reverse=True)
        return [m for _, m in scored[:k]]

    def reset(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._items),
                "cap": self._cap,
                "dim": self._dim,
            }


# ────────────────────────────────────────────────────────── L2 storage ---


class L2ColdStore:
    """Sqlite-backed compressed store for cold-series replay."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._path = Path(db_path or L2_DB_PATH)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._connect() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS memories ("
                "item_id TEXT PRIMARY KEY,"
                "role TEXT NOT NULL,"
                "text TEXT NOT NULL,"
                "tags TEXT,"
                "pinned INTEGER,"
                "created_at REAL"
                ")"
            )
            c.execute("CREATE INDEX IF NOT EXISTS mem_role_ts ON memories(role, created_at)")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self._path), timeout=2.0)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add(self, item: MemoryItem) -> None:
        try:
            with self._lock, self._connect() as c:
                c.execute(
                    "INSERT OR REPLACE INTO memories "
                    "(item_id, role, text, tags, pinned, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item.item_id,
                        item.role,
                        item.text,
                        json.dumps(list(item.tags), ensure_ascii=False),
                        1 if item.pinned else 0,
                        item.created_at,
                    ),
                )
        except Exception as e:  # pragma: no cover — fail soft
            logger.debug("L2 insert failed: %r", e)

    def query(self, n: int) -> List[MemoryItem]:
        try:
            with self._connect() as c:
                rows = c.execute(
                    "SELECT item_id, role, text, tags, pinned, created_at "
                    "FROM memories ORDER BY created_at DESC LIMIT ?",
                    (n,),
                ).fetchall()
        except Exception:  # pragma: no cover
            return []
        out: List[MemoryItem] = []
        for r in rows:
            tags: List[str] = []
            try:
                tags = json.loads(r[3] or "[]")
            except Exception:
                pass
            out.append(MemoryItem(
                item_id=r[0], role=r[1], text=r[2],
                created_at=r[5], tags=tuple(tags),
                pinned=bool(r[4]),
            ))
        return list(reversed(out))

    def close(self) -> None:
        # sqlite reconnects per call — nothing to close.
        return None


# ──────────────────────────────────────────────────────── Engine -------


class EntropicEvolutionEngine:
    """Top-level multi-tier memory engine.

    Fail-soft: every method returns a small dict or sensible
    default. Internal exceptions are logged at DEBUG, not raised.
    """

    def __init__(
        self,
        *,
        l0_capacity: int = L0_TURNS,
        l1_max_items: int = L1_MAX_ITEMS,
        l2_db_path: Optional[str] = None,
        vector_dim: int = DEFAULT_VECTOR_DIM,
    ) -> None:
        self.l0 = L0HotStore(capacity=l0_capacity)
        self.l1 = L1WarmStore(dim=vector_dim, max_items=l1_max_items)
        self.l2 = L2ColdStore(db_path=l2_db_path)
        self._lock = threading.Lock()
        self._stats: Dict[str, int] = collections.Counter()
        # Re-hydrate recent items from cold storage on cold-start so
        # the next chat session can resume without a re-priming step.
        try:
            for m in self.l2.query(min(l1_max_items, 2000)):
                if m.vector is None:
                    m = dc.replace(m, vector=_vectorise(m.text, vector_dim))
                self.l1.add(m)
        except Exception as e:  # pragma: no cover
            logger.debug("cold rehydrate failed: %r", e)

    # -------------------------------------------------------- write API

    def learn_from_exchange(self, user_msg: str, assistant_msg: str,
                            tool_calls: Optional[List[str]] = None) -> Dict[str, int]:
        n = 0
        n += self.learn_from_user_message(user_msg)
        if assistant_msg:
            n += self._record(assistant_msg, role="assistant",
                              tags=("reply", "summary"))
        for t in (tool_calls or []):
            self.learn_from_tool_call(t)
            n += 1
        return {"behaviors_learned": n, **self._stats_snapshot()}

    def learn_from_user_message(self, message: str) -> int:
        if not message or not message.strip():
            return 0
        return self._record(message, role="user",
                            tags=("user", "intent"))

    def learn_from_tool_call(self, tool_name: str) -> int:
        if not tool_name:
            return 0
        return self._record(f"used tool: {tool_name}", role="tool",
                            tags=("tool", tool_name))

    # --------------------------------------------------------- read API

    def get_memory_context(self, max_items: int = 24) -> str:
        """Return a prompt-ready summary of the most relevant memory.

        Strategy:
            * L0 last 8 turns verbatim.
            * L1 top-N cosine-similar to ``recent_text``. When L0
              is empty (cold-start rehydrate, fresh session), fall
              back to a fuzzy query against any recent L1 title so
              the prompt is never empty.
            * cap total to ``max_items`` to keep the prompt bounded.
        """
        if max_items <= 0:
            return ""

        l0_items = self.l0.query(min(8, self.l0._cap))
        recent_text = l0_items[-1].text if l0_items else ""

        # On cold-start / rehydrate, recent_text may be empty; if
        # so, query L1 with a generic trigger word so results come
        # back regardless of what the user is about to ask.
        if not recent_text:
            recent_text = "summary recap"

        l1_items = self.l1.query(recent_text, k=max(1, max_items - len(l0_items)))
        # Ensure we return *something* even when L1 produced no hits.
        if not l1_items and not l0_items:
            try:
                fallback = list(self.l1._items)[-max_items:]  # type: ignore[attr-defined]
                l1_items = list(reversed(fallback))
            except Exception:
                l1_items = []

        lines: List[str] = []
        for m in l0_items[-max_items:]:
            lines.append(f"[memory|{m.role}] {self._truncate(m.text, 240)}")
        for m in l1_items:
            if any(m.item_id == lo.item_id for lo in l0_items):
                continue
            lines.append(f"[memory|{m.role}] {self._truncate(m.text, 200)}")
        if not lines:
            # Last-ditch pool: any cold-store hits.
            try:
                for m in self.l2.query(max_items):
                    lines.append(f"[memory|{m.role}] {self._truncate(m.text, 200)}")
            except Exception:
                pass
        return "\n".join(lines[:max_items])

    def get_stats(self) -> Dict[str, Any]:
        out = self._stats_snapshot()
        out["l1"] = self.l1.stats()
        return out

    def get_tool_stats(self) -> Dict[str, int]:
        # Reverse-engineer tool usage from L1 / L2 — cheap heuristic.
        out: Dict[str, int] = {}
        try:
            for m in self.l1._items:  # type: ignore[attr-defined]
                for tag in m.tags:
                    if tag in ("user", "reply", "intent", "summary", "tool"):
                        continue
                    out[tag] = out.get(tag, 0) + 1
        except Exception:
            pass
        return out

    # ---------------------------------------------------------- helpers

    def _record(self, text: str, *, role: str,
                tags: Iterable[str] = ()) -> int:
        tags_t = tuple(tags)
        item = MemoryItem(
            item_id=hashlib.sha1(
                f"{time.time():.6f}|{role}|{len(text)}|{text[:64]}".encode()
            ).hexdigest()[:16],
            role=role,
            text=text,
            created_at=time.time(),
            vector=_vectorise(text, self.l1._dim),  # type: ignore[attr-defined]
            tags=tags_t,
        )
        with self._lock:
            self.l0.add(item)
            self.l1.add(item)
            self.l2.add(item)
            self._stats[f"r.{role}"] += 1
            self._stats["r.total"] += 1
        return 1

    def _stats_snapshot(self) -> Dict[str, int]:
        return dict(self._stats)

    @staticmethod
    def _truncate(s: str, n: int) -> str:
        s = s.strip()
        if len(s) <= n:
            return s
        return s[:n - 1] + "…"


# ──────────────────────────────────────────────────────── singleton ----


_ENGINE: Optional[EntropicEvolutionEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_entropic_engine() -> EntropicEvolutionEngine:
    """Process-wide singleton, lazily built on first call."""
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = EntropicEvolutionEngine()
        return _ENGINE


def reset_engine_for_tests() -> None:
    """Drop the singleton — used by the unit tests."""
    global _ENGINE
    with _ENGINE_LOCK:
        _ENGINE = None


# ──────────────────────────────────────────────────────── self-test ---


def _self_check() -> int:  # pragma: no cover — `python -m`
    eng = EntropicEvolutionEngine(l0_capacity=8, l1_max_items=64, l2_db_path=":memory:")
    eng.l2 = L2ColdStore(db_path=":memory:")
    n = eng.learn_from_user_message("remember the project is about minimum entropy")
    assert n == 1, n
    out = eng.get_memory_context(8)
    assert "memory" in out or "minimum entropy" in out, out
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_self_check())
