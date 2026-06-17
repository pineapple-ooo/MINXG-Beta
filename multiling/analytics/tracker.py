"""Analytics tracker — see __init__.py."""
from collections import Counter
from typing import Dict, Any

class AnalyticsTracker:
    def __init__(self):
        self._events: Counter = Counter()
    def track(self, event: str, properties: Dict[str, Any] = None):
        self._events[event] += 1
    def get_stats(self) -> Dict[str, int]:
        return dict(self._events)

_tracker = AnalyticsTracker()
track_event = _tracker.track
get_stats = _tracker.get_stats
