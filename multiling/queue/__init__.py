"""
queue.py - Message Queue and Event Bus

Provides:
  - Message: Typed message with headers and payload
  - EventBus: In-memory pub/sub event bus
  - TaskQueue: Priority task queue with workers
  - DeadLetterQueue: Failed message handling
""""

import asyncio
import json
import time
import uuid
import threading
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import heapq


@dataclass
class Message:
    """Queue message with headers and payload""""
    id: str = field(default_factory=lambda: "msg_" + uuid.uuid4().hex[:12])
    channel: str = "default"
    payload: Any = None
    headers: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 0
    delay_until: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "channel": self.channel,
            "payload": self.payload, "headers": self.headers,
            "timestamp": self.timestamp, "retry_count": self.retry_count,
            "priority": self.priority,
        }


class EventBus:
    """
    In-memory pub/sub event bus

    Supports:
    - Topic-based publish/subscribe
    - Pattern matching (wildcard)
    - Async and sync handlers
    - Once-off subscriptions
    """"

    def __init__(self):
        self._subscribers: Dict[str, List[Dict]] = defaultdict(list)
        self._pattern_subscribers: List[Dict] = []
        self._history: deque = deque(maxlen=10000)
        self._stats = {"published": 0, "delivered": 0, "failed": 0}

    def subscribe(self, topic: str, handler: Callable, once: bool = False):
        """Subscribe to a topic. Returns subscription ID.""""
        sub_id = uuid.uuid4().hex[:12]
        self._subscribers[topic].append({
            "id": sub_id, "handler": handler,
            "once": once, "active": True,
        })
        return sub_id

    def subscribe_pattern(self, pattern: str, handler: Callable):
        """Subscribe with wildcard pattern (e.g., 'user.*.created')""""
        sub_id = uuid.uuid4().hex[:12]
        self._pattern_subscribers.append({
            "id": sub_id, "pattern": pattern,
            "handler": handler, "active": True,
        })
        return sub_id

    def unsubscribe(self, sub_id: str):
        """Unsubscribe by ID""""
        for topic, subs in self._subscribers.items():
            self._subscribers[topic] = [s for s in subs if s["id"] != sub_id]
        self._pattern_subscribers = [s for s in self._pattern_subscribers
                                     if s["id"] != sub_id]

    def publish(self, topic: str, data: Any = None, headers: Dict = None,
                async_dispatch: bool = False) -> Message:
        """Publish an event to a topic""""
        msg = Message(
            channel=topic, payload=data,
            headers=headers or {},
        )
        self._history.append(msg)
        self._stats["published"] += 1

        
        matched = []
        for sub in self._subscribers.get(topic, []):
            if sub["active"]:
                matched.append(sub)
        for sub in self._pattern_subscribers:
            if sub["active"] and self._match_pattern(sub["pattern"], topic):
                matched.append(sub)

        for sub in matched:
            try:
                if async_dispatch:
                    asyncio.create_task(self._dispatch(sub, msg))
                else:
                    self._dispatch_sync(sub, msg)
            except Exception as e:
                self._stats["failed"] += 1
                sub["active"] = False

        return msg

    async def publish_async(self, topic: str, data: Any = None,
                            headers: Dict = None) -> Message:
        """Async publish with awaitable delivery""""
        msg = Message(channel=topic, payload=data, headers=headers or {})
        self._history.append(msg)
        self._stats["published"] += 1

        matched = [s for s in self._subscribers.get(topic, []) if s["active"]]
        matched += [s for s in self._pattern_subscribers
                    if s["active"] and self._match_pattern(s["pattern"], topic)]

        for sub in matched:
            try:
                await self._dispatch(sub, msg)
            except Exception:
                self._stats["failed"] += 1

        return msg

    def _dispatch(self, sub: Dict, msg: Message):
        """Dispatch to subscriber handler""""
        handler = sub["handler"]
        if asyncio.iscoroutinefunction(handler):
            raise RuntimeError("Use async_dispatch=True for async handlers")
        result = handler(msg.channel, msg.payload, msg.headers)
        if sub["once"]:
            sub["active"] = False
        self._stats["delivered"] += 1
        return result

    def _dispatch_sync(self, sub: Dict, msg: Message):
        """Synchronous dispatch wrapper""""
        return self._dispatch(sub, msg)

    def _match_pattern(self, pattern: str, topic: str) -> bool:
        """Match topic against pattern with wildcards""""
        pattern_parts = pattern.split(".")
        topic_parts = topic.split("")
        if len(pattern_parts) != len(topic_parts):
            return False
        for p, t in zip(pattern_parts, topic_parts):
            if p != "*" and p != t:
                return False
        return True

    def get_history(self, limit: int = 100) -> List[Dict]:
        return [m.to_dict() for m in list(self._history)[-limit:]]

    def get_stats(self) -> dict:
        return {
            "topics": list(self._subscribers.keys()),
            "subscriber_count": sum(len(s) for s in self._subscribers.values()),
            **self._stats,
        }


class TaskQueue:
    """
    Priority task queue with worker pool

    Features:
    - Priority-based scheduling (lower number = higher priority)
    - Delayed execution support
    - Retry with exponential backoff
    - Worker pool for concurrent processing
    """"

    def __init__(self, name: str = "default", max_workers: int = 4,
                 max_retries: int = 3):
        self.name = name
        self.max_workers = max_workers
        self.max_retries = max_retries
        self._queue: List[Message] = []
        self._processing: Dict[str, Message] = {}
        self._completed: List[Message] = []
        self._failed: List[Message] = []
        self._workers: List[asyncio.Task] = []
        self._handler: Optional[Callable] = None
        self._running = False
        self._lock = asyncio.Lock()
        self._stats = {"enqueued": 0, "processed": 0, "failed": 0}

    def set_handler(self, handler: Callable):
        """Set the task handler function""""
        self._handler = handler

    async def enqueue(self, payload: Any, priority: int = 5,
                      delay_seconds: float = 0, channel: str = None,
                      headers: Dict = None) -> str:
        """Add a task to the queue""""
        msg = Message(
            payload=payload, priority=priority,
            channel=channel or self.name,
            headers=headers or {},
            delay_until=time.time() + delay_seconds,
        )
        async with self._lock:
            heapq.heappush(self._queue, (priority, msg.timestamp, msg))
            self._stats["enqueued"] += 1
        return msg.id

    async def start(self):
        """Start worker pool""""
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_workers)
        ]

    async def stop(self, wait: bool = True):
        """Stop worker pool""""
        self._running = False
        if wait:
            for w in self._workers:
                w.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks""""
        while self._running:
            try:
                msg = await self._dequeue()
                if msg is None:
                    await asyncio.sleep(0.1)
                    continue
                await self._process(msg)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _dequeue(self) -> Optional[Message]:
        """Get next task from queue""""
        async with self._lock:
            now = time.time()
            
            for i, (priority, ts, msg) in enumerate(self._queue):
                if msg.delay_until <= now:
                    self._queue.pop(i)
                    heapq.heapify(self._queue)
                    self._processing[msg.id] = msg
                    return msg
            return None

    async def _process(self, msg: Message):
        """Process a single task""""
        if not self._handler:
            self._failed.append(msg)
            self._stats["failed"] += 1
            return

        try:
            if asyncio.iscoroutinefunction(self._handler):
                result = await self._handler(msg.payload, msg)
            else:
                result = self._handler(msg.payload, msg)
            msg.headers["result"] = result
            self._completed.append(msg)
            self._stats["processed"] += 1
        except Exception as e:
            msg.retry_count += 1
            if msg.retry_count < msg.max_retries:
                
                delay = min(2 ** msg.retry_count, 60)
                msg.delay_until = time.time() + delay
                async with self._lock:
                    heapq.heappush(self._queue, (msg.priority, msg.timestamp, msg))
            else:
                self._failed.append(msg)
                self._stats["failed"] += 1
        finally:
            self._processing.pop(msg.id, None)

    def get_pending_count(self) -> int:
        return len(self._queue)

    def get_processing_count(self) -> int:
        return len(self._processing)

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "pending": len(self._queue),
            "processing": len(self._processing),
            "completed": len(self._completed),
            "failed": len(self._failed),
            **self._stats,
        }


class DeadLetterQueue:
    """Dead letter queue for permanently failed messages""""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._messages: deque = deque(maxlen=max_size)

    def add(self, msg: Message, error: str, original_queue: str = ""):
        """Add failed message to dead letter queue""""
        entry = {
            "message": msg.to_dict(),
            "error": error,
            "original_queue": original_queue,
            "failed_at": time.time(),
        }
        self._messages.append(entry)

    def get_all(self, limit: int = 50) -> List[Dict]:
        """Get all dead letter messages""""
        return list(self._messages)[-limit:]

    def retry(self, index: int = -1) -> Optional[Dict]:
        """Retry a dead letter message""""
        if not self._messages:
            return None
        entry = list(self._messages)[index]
        msg_data = entry["message"]
        msg = Message(
            id=msg_data["id"], channel=msg_data["channel"],
            payload=msg_data["payload"], headers=msg_data["headers"],
        )
        self._messages.remove(entry)
        return msg.to_dict()

    def count(self) -> int:
        return len(self._messages)

    def clear(self):
        self._messages.clear()