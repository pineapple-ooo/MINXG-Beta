"""

"""
from __future__ import annotations
import time
import asyncio
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Any, Callable
from minxg.base import BaseWorker, tool


class Event:
    def __init__(self, event_type: str, data: Any = None, source: str = "",
                 metadata: dict = None, tags: list = None):
        self.event_id = f"evt-{uuid.uuid4().hex[:8]}"
        self.event_type = event_type
        self.data = data
        self.source = source
        self.metadata = metadata or {}
        self.tags = tags or []
        self.created_at = time.time()

    def to_dict(self) -> Dict:
        return {"event_id": self.event_id, "type": self.event_type,
                "data": self.data, "source": self.source,
                "metadata": self.metadata, "tags": self.tags,
                "created_at": self.created_at}


class EventsWorker(BaseWorker):
    worker_id = "events"
    version = "1.0.0"

    def __init__(self):
        self._handlers: Dict[str, List[Dict]] = defaultdict(list)  
        self._history: List[Event] = []
        self._max_history = 1000
        self._pending: List[asyncio.Task] = []
        self._stats = {"published": 0, "delivered": 0, "errors": 0}
        self._start_time = time.time()
        self.tools: Dict = {}
        self._register_tools()

    @tool(description="Subscribe to event pattern (wildcards supported)", category="subscribe")
    async def subscribe(self, pattern: str, handler_id: str = "",
                       priority: int = 100) -> Dict:
        if not handler_id:
            handler_id = f"h-{uuid.uuid4().hex[:8]}"
        self._handlers[pattern].append({
            "handler_id": handler_id, "fn": None,
            "priority": priority, "hits": 0, "created_at": time.time(),
        })
        return {"handler_id": handler_id, "pattern": pattern, "subscribed": True}

    @tool(description="Unsubscribe", category="subscribe")
    async def unsubscribe(self, pattern: str, handler_id: str) -> Dict:
        for i, h in enumerate(self._handlers[pattern]):
            if h["handler_id"] == handler_id:
                self._handlers[pattern].pop(i)
                return {"handler_id": handler_id, "unsubscribed": True}
        return {"error": f"handler not found: {handler_id}"}

    @tool(description="List all subscriptions for a pattern", category="subscribe")
    async def list_handlers(self, pattern: str = "") -> Dict:
        if pattern:
            handlers = [{"pattern": pattern, **h} for h in self._handlers.get(pattern, [])]
        else:
            handlers = []
            for pat, hs in self._handlers.items():
                for h in hs:
                    handlers.append({"pattern": pat, **h})
        return {"count": len(handlers), "handlers": handlers}

    @tool(description="Publish event, async trigger all matching handlers", category="publish")
    async def publish(self, event_type: str, data: Any = None,
                     source: str = "", metadata: dict = None,
                     tags: list = None, wait: bool = False) -> Dict:
        evt = Event(event_type, data, source, metadata, tags)
        self._history.append(evt)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        self._stats["published"] += 1

        handlers = []
        for pattern, hs in self._handlers.items():
            if self._match_pattern(pattern, event_type):
                for h in hs:
                    if h["fn"] is not None:
                        handlers.append(h)
        handlers.sort(key=lambda h: -h["priority"])

        if not handlers:
            return {"event_id": evt.event_id, "type": event_type,
                    "delivered": 0, "handlers_matched": 0}

        if wait:
            for h in handlers:
                try:
                    fn = h["fn"]
                    if asyncio.iscoroutinefunction(fn):
                        await fn(evt.to_dict())
                    else:
                        fn(evt.to_dict())
                    h["hits"] += 1
                    self._stats["delivered"] += 1
                except Exception as e:
                    self._stats["errors"] += 1
                    self._history.append({"error": str(e), "handler": h["handler_id"],
                                          "at": time.time()})
            return {"event_id": evt.event_id, "type": event_type,
                    "delivered": len(handlers), "wait": True}
        else:
            for h in handlers:
                task = asyncio.create_task(self._deliver(h, evt))
                self._pending.append(task)
            return {"event_id": evt.event_id, "type": event_type,
                    "delivered_async": len(handlers), "wait": False}

    async def _deliver(self, handler: Dict, evt: Event):
        try:
            fn = handler["fn"]
            if asyncio.iscoroutinefunction(fn):
                await fn(evt.to_dict())
            else:
                fn(evt.to_dict())
            handler["hits"] += 1
            self._stats["delivered"] += 1
        except Exception as e:
            self._stats["errors"] += 1
            self._history.append({"error": str(e), "handler": handler["handler_id"],
                                  "at": time.time()})

    def _match_pattern(self, pattern: str, event_type: str) -> bool:
        if pattern == event_type:
            return True
        if pattern == "*":
            return True
        if "*" in pattern:
            regex = "^" + pattern.replace(".", r"\.").replace("*", "[^.]+") + "$"
            import re
            return bool(re.match(regex, event_type))
        return False

    @tool(description="View recent N events", category="info")
    async def get_history(self, event_type: str = "", limit: int = 50) -> Dict:
        items = self._history
        if event_type:
            items = [e for e in items if hasattr(e, "event_type")
                     and e.event_type == event_type]
        return {"count": len(items),
                "events": [e.to_dict() if hasattr(e, "to_dict") else e
                           for e in items[-limit:]]}

    @tool(description="Clear history", category="info")
    async def clear_history(self) -> Dict:
        n = len(self._history)
        self._history.clear()
        return {"cleared": n}

    @tool(description="Event bus statistics", category="info")
    async def stats(self) -> Dict:
        return {
            **self._stats,
            "subscribers": sum(len(hs) for hs in self._handlers.values()),
            "patterns": list(self._handlers.keys()),
            "history_size": len(self._history),
            "uptime_sec": round(time.time() - self._start_time, 2),
        }

    @tool(description="Event bus health check", category="info")
    async def health(self) -> Dict:
        return {"status": "ok", "handlers": sum(len(hs) for hs in self._handlers.values()),
                "events_processed": self._stats.get("published", 0),
                "errors": self._stats.get("errors", 0),
                "pending": len(self._pending)}

    @tool(description="List all subscribers and their patterns", category="info")
    async def list_subscribers(self) -> Dict:
        subs = {pat: [{"id": h["handler_id"], "desc": h.get("description", "")}
                       for h in handlers]
                for pat, handlers in self._handlers.items()}
        return {"subscribers": subs, "pattern_count": len(subs)}
