"""analytics.tracker — Rolling-window event tracker.

Designed to be embedded by Observability cells without forcing a global
import. The tracker is thread-safe and uses a fixed-size rolling window so
memory stays bounded regardless of event rate.
""""
from __future__ import annotations
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TrackedEvent:
    name: str
    timestamp: float
    properties: Tuple[Tuple[str, Any], ...] = field(default_factory=tuple)


class AnalyticsTracker:
    def __init__(self, window_size: int = 1000) -> None:
        self._events: Deque[TrackedEvent] = deque(maxlen=window_size)
        self._counters: Counter = Counter()
        self._lock = threading.Lock()

    def track(self, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
        props_tuple = tuple(sorted((properties or {}).items()))
        record = TrackedEvent(event, time.time(), props_tuple)
        with self._lock:
            self._events.append(record)
            self._counters[event] += 1

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def recent(self, limit: int = 50) -> List[TrackedEvent]:
        with self._lock:
            return list(self._events)[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._counters.clear()

    def rate(self, event: str, since_seconds: float = 60.0) -> float:
        cutoff = time.time() - since_seconds
        with self._lock:
            hits = sum(1 for e in self._events if e.name == event and e.timestamp >= cutoff)
        return hits / since_seconds


_tracker = AnalyticsTracker()
track_event = _tracker.track
get_stats = _tracker.get_stats
recent_events = _tracker.recent
event_rate = _tracker.rate
clear_events = _tracker.clear
