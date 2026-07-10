"""
set_state, get_state, delete_state, find_by_tag, store_episode, recall_episodes
"""
from __future__ import annotations
import time
import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any
from minxg.base import BaseWorker, tool


@dataclass
class SessionState:
    session_id: str
    created_at: float
    last_access: float
    state: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl_seconds: int = 3600

    def touch(self):
        self.last_access = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_access) > self.ttl_seconds

    def to_dict(self) -> Dict:
        return {**asdict(self), "expired": self.is_expired()}


class StateSessionWorker(BaseWorker):
    facade_alias = "state_session"
    worker_id = "state_session"
    version = "0.17.0"

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._states: Dict[str, Any] = {}
        self._episodes: Dict[str, List[Dict]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()
        self.tools: Dict = {}
        self._start_time = time.time()
        self._register_tools()

    @tool(description="Create session, return session_id", category="session")
    async def create_session(self, session_id: str = "", config: dict = None,
                            ttl_seconds: int = 3600) -> Dict:
        async with self._global_lock:
            sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
            if sid in self._sessions:
                return {"error": f"session exists: {sid}"}
            sess = SessionState(
                session_id=sid, created_at=time.time(), last_access=time.time(),
                metadata=config or {}, ttl_seconds=ttl_seconds,
            )
            self._sessions[sid] = sess
            return {"session_id": sid, "created": True, "ttl": ttl_seconds}

    @tool(description="Get session details", category="session")
    async def get_session(self, session_id: str) -> Dict:
        sess = self._sessions.get(session_id)
        if not sess:
            return {"error": f"session not found: {session_id}"}
        if sess.is_expired():
            return {"error": f"session expired: {session_id}", "expired": True}
        sess.touch()
        return sess.to_dict()

    @tool(description="Delete session", category="session")
    async def delete_session(self, session_id: str) -> Dict:
        existed = session_id in self._sessions
        self._sessions.pop(session_id, None)
        self._episodes.pop(session_id, None)
        return {"session_id": session_id, "deleted": existed}

    @tool(description="List all active sessions", category="session")
    async def list_sessions(self, include_expired: bool = False) -> Dict:
        sessions = []
        for s in self._sessions.values():
            if not include_expired and s.is_expired():
                continue
            sessions.append({"session_id": s.session_id,
                             "created_at": s.created_at,
                             "last_access": s.last_access,
                             "history_len": len(s.history),
                             "ttl": s.ttl_seconds})
        return {"count": len(sessions), "sessions": sessions}

    @tool(description="Set key=value, optional tags/ttl/owner", category="kv")
    async def set_state(self, key: str, value, owner: str = "",
                       tags: dict = None, ttl_seconds: int = 0) -> Dict:
        async with self._locks[f"kv:{key}"]:
            entry = {
                "key": key, "value": value, "owner": owner,
                "tags": tags or {}, "set_at": time.time(),
                "ttl_seconds": ttl_seconds,
            }
            self._states[key] = entry
        return {"key": key, "set": True, "ttl": ttl_seconds}

    @tool(description="Get value by key, supports default fallback", category="kv")
    async def get_state(self, key: str, default: Any = None) -> Dict:
        entry = self._states.get(key)
        if not entry:
            return {"key": key, "found": False, "value": default}
        if entry["ttl_seconds"] > 0 and \
           (time.time() - entry["set_at"]) > entry["ttl_seconds"]:
            self._states.pop(key, None)
            return {"key": key, "found": False, "value": default, "expired": True}
        return {"key": key, "found": True, "value": entry["value"],
                "tags": entry.get("tags", {}), "owner": entry.get("owner", "")}

    @tool(description="Delete key", category="kv")
    async def delete_state(self, key: str) -> Dict:
        existed = key in self._states
        self._states.pop(key, None)
        return {"key": key, "deleted": existed}

    @tool(description="Search keys by tag", category="kv")
    async def find_by_tag(self, tag_key: str, tag_value: str = "") -> Dict:
        results = []
        for k, e in self._states.items():
            tags = e.get("tags", {})
            if tag_key in tags and (not tag_value or tags[tag_key] == tag_value):
                results.append({"key": k, "value": e["value"], "tags": tags})
        return {"tag": {tag_key: tag_value}, "count": len(results), "results": results}

    @tool(description="Store a conversation turn (session_id/role/content)", category="memory")
    async def store_episode(self, session_id: str, role: str, content: str,
                          metadata: dict = None) -> Dict:
        async with self._locks[f"ep:{session_id}"]:
            ep = {"role": role, "content": content, "at": time.time(),
                  "metadata": metadata or {}}
            self._episodes[session_id].append(ep)
            if len(self._episodes[session_id]) > 1000:
                self._episodes[session_id] = self._episodes[session_id][-1000:]
        return {"session_id": session_id, "stored": True, "total": len(self._episodes[session_id])}

    @tool(description="Get last N turns of a session", category="memory")
    async def recall_episodes(self, session_id: str, limit: int = 20) -> Dict:
        eps = self._episodes.get(session_id, [])
        return {"session_id": session_id, "count": len(eps),
                "episodes": eps[-limit:] if limit > 0 else eps}

    @tool(description="Get worker statistics", category="info")
    async def get_stats(self) -> Dict:
        return {
            "sessions": len(self._sessions),
            "active_sessions": sum(1 for s in self._sessions.values() if not s.is_expired()),
            "states": len(self._states),
            "episodes": sum(len(v) for v in self._episodes.values()),
            "uptime_sec": round(time.time() - self._start_time, 2),
        }
