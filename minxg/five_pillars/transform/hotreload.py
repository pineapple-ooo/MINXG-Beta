"""

"""
from __future__ import annotations
import os
import time
import asyncio
import importlib
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from minxg.base import BaseWorker, tool


class HotReloadWorker(BaseWorker):
    worker_id = "hotreload"
    version = "0.16.0"

    def __init__(self):
        self._watches: Dict[str, Dict] = {}    
        self._polling_task: Optional[asyncio.Task] = None
        self._poll_interval = 1.0
        self._events: List[Dict] = []
        self._max_events = 500
        self._start_time = time.time()
        self.tools: Dict = {}
        self._register_tools()

    @tool(description="Start watching files/directories for changes", category="watch")
    async def watch(self, paths: list, watch_id: str = "",
                   poll_interval: float = 1.0,
                   pattern: str = "**/*") -> Dict:
        """
        """
        if not watch_id:
            watch_id = f"w-{uuid.uuid4().hex[:8]}"
        if watch_id in self._watches:
            return {"error": f"watch_id exists: {watch_id}"}

        mtimes = self._scan(paths, pattern)
        self._watches[watch_id] = {
            "watch_id": watch_id, "paths": paths, "pattern": pattern,
            "mtimes": mtimes, "callback": None,
            "last_change": None, "change_count": 0,
            "created_at": time.time(), "poll_interval": poll_interval,
        }
        if self._polling_task is None or self._polling_task.done():
            self._polling_task = asyncio.create_task(self._poll_loop())
        return {"watch_id": watch_id, "files": len(mtimes), "started": True}

    @tool(description="Cancel watching", category="watch")
    async def unwatch(self, watch_id: str) -> Dict:
        w = self._watches.pop(watch_id, None)
        if not w:
            return {"error": f"watch not found: {watch_id}"}
        return {"watch_id": watch_id, "removed": True,
                "total_changes": w["change_count"]}

    @tool(description="List all watchers", category="watch")
    async def list_watches(self) -> Dict:
        return {"count": len(self._watches),
                "watches": [{"watch_id": wid, "paths": w["paths"],
                             "files": len(w["mtimes"]),
                             "changes": w["change_count"],
                             "last_change": w["last_change"]}
                            for wid, w in self._watches.items()]}

    async def _poll_loop(self):
        while self._watches:
            try:
                for wid, w in list(self._watches.items()):
                    new_mtimes = self._scan(w["paths"], w["pattern"])
                    changes = self._diff(w["mtimes"], new_mtimes)
                    if changes:
                        w["mtimes"] = new_mtimes
                        w["change_count"] += len(changes)
                        w["last_change"] = time.time()
                        evt = {"watch_id": wid, "changes": changes, "at": time.time()}
                        self._events.append(evt)
                        if len(self._events) > self._max_events:
                            self._events = self._events[-self._max_events:]
                        if w["callback"]:
                            try:
                                cb = w["callback"]
                                if asyncio.iscoroutinefunction(cb):
                                    await cb(evt)
                                else:
                                    cb(evt)
                            except Exception as e:
                                self._events.append({"error": str(e),
                                                     "watch_id": wid,
                                                     "at": time.time()})
            except Exception as e:
                self._events.append({"error": str(e), "at": time.time()})
            min_interval = min((w.get("poll_interval", self._poll_interval)
                                for w in self._watches.values()), default=self._poll_interval)
            await asyncio.sleep(min_interval)

    def _scan(self, paths: list, pattern: str) -> Dict[str, float]:
        result = {}
        for p in paths:
            pp = Path(p)
            if pp.is_file():
                try:
                    result[str(pp)] = pp.stat().st_mtime
                except OSError:
                    pass
            elif pp.is_dir():
                for f in pp.glob(pattern):
                    if f.is_file():
                        try:
                            result[str(f)] = f.stat().st_mtime
                        except OSError:
                            pass
        return result

    def _diff(self, old: Dict[str, float], new: Dict[str, float]) -> List[Dict]:
        changes = []
        for path, mtime in new.items():
            if path not in old:
                changes.append({"path": path, "type": "added", "mtime": mtime})
            elif old[path] != mtime:
                changes.append({"path": path, "type": "modified", "mtime": mtime})
        for path in old:
            if path not in new:
                changes.append({"path": path, "type": "deleted",
                                "old_mtime": old[path]})
        return changes

    @tool(description="Reload Python module (dotted name)",
          category="reload")
    async def reload_module(self, module_name: str) -> Dict:
        try:
            mod = importlib.import_module(module_name)
            importlib.reload(mod)
            return {"module": module_name, "reloaded": True, "file": getattr(mod, "__file__", "?")}
        except Exception as e:
            return {"module": module_name, "error": str(e),
                    "error_type": type(e).__name__}

    @tool(description="View file change history", category="info")
    async def events(self, watch_id: str = "", limit: int = 50) -> Dict:
        items = self._events
        if watch_id:
            items = [e for e in items if e.get("watch_id") == watch_id]
        return {"count": len(items), "items": items[-limit:]}

    @tool(description="Overall statistics", category="info")
    async def stats(self) -> Dict:
        return {
            "active_watches": len(self._watches),
            "total_events": len(self._events),
            "polling_active": self._polling_task is not None and
                               not self._polling_task.done(),
            "uptime_sec": round(time.time() - self._start_time, 2),
        }

    @tool(description="Hot-reload health check", category="info")
    async def health(self) -> Dict:
        return {"status": "ok", "active_watches": len(self._watches),
                "watching": list(self._watches.keys()),
                "polling_active": self._polling_task is not None and not self._polling_task.done(),
                "last_event": self._events[-1] if self._events else None}

    @tool(description="Get recent hot-reload events", category="info")
    async def recent_events(self, count: int = 10) -> Dict:
        return {"events": self._events[-count:], "total": len(self._events), "count": min(count, len(self._events))}
