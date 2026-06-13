"""
analytics.py - System monitoring and data analysis module

Provides:
  - MetricsCollector: Multi-dimensional metrics collection
  - AnalyticsEngine: Real-time analysis engine with threshold alerting
  - HealthMonitor: System health monitoring with pluggable checks
  - PerformanceTracker: Performance span tracking
  - UsageAnalytics: Usage event tracking and reporting
"""

import asyncio
import json
import time
import os
import threading
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from datetime import datetime, timedelta


@dataclass
class Metric:
    """A single metric data point"""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp_iso"] = datetime.fromtimestamp(self.timestamp).isoformat()
        return d


class MetricsCollector:
    """Multi-dimensional metrics collector with counters, gauges, and histograms"""

    def __init__(self, prefix="minxg", max_points=10000):
        self.prefix = prefix
        self.max_points = max_points
        self._metrics = defaultdict(lambda: deque(maxlen=max_points))
        self._counters = defaultdict(int)
        self._gauges = {}
        self._histograms = defaultdict(list)
        self._lock = threading.Lock()

    def counter(self, name, amount=1, tags=None):
        """Increment a counter metric"""
        key = self._build_key(name, tags)
        with self._lock:
            self._counters[key] += amount
            self._metrics[key].append(Metric(
                name=name, value=self._counters[key],
                tags=tags or {}, unit="count",
            ))

    def gauge(self, name, value, tags=None):
        """Set a gauge metric (current value snapshot)"""
        key = self._build_key(name, tags)
        with self._lock:
            self._gauges[key] = value
            self._metrics[key].append(Metric(
                name=name, value=value,
                tags=tags or {}, unit="gauge",
            ))

    def histogram(self, name, value, tags=None):
        """Record a histogram metric (distribution tracking)"""
        key = self._build_key(name, tags)
        with self._lock:
            self._histograms[key].append(value)
            if len(self._histograms[key]) > 10000:
                self._histograms[key] = self._histograms[key][-5000:]
            self._metrics[key].append(Metric(
                name=name, value=value,
                tags=tags or {}, unit="histogram",
            ))

    def timer(self, name, duration_ms, tags=None):
        """Record a timer metric (duration + count)"""
        self.histogram(name + "_duration", duration_ms, tags)
        self.counter(name + "_count", tags=tags)

    def _build_key(self, name, tags=None):
        if tags:
            parts = [self.prefix, name]
            for k, v in sorted(tags.items()):
                parts.extend([k, str(v)])
            return "_".join(parts)
        return self.prefix + "_" + name

    def get_metric(self, name):
        """Get metric history by name (exact or partial match)"""
        with self._lock:
            key = self.prefix + "_" + name
            if key in self._metrics:
                return list(self._metrics[key])
            results = []
            for k, v in self._metrics.items():
                if name in k:
                    results.extend(v)
            return results if results else None

    def get_all_keys(self):
        with self._lock:
            return list(self._metrics.keys())

    def snapshot(self):
        """Get current snapshot of all metrics"""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histogram_summaries": {
                    k: self._histogram_stats(v)
                    for k, v in self._histograms.items()
                },
            }

    def _histogram_stats(self, values):
        if not values:
            return {"count": 0}
        sorted_v = sorted(values)
        n = len(sorted_v)
        return {
            "count": n,
            "min": sorted_v[0],
            "max": sorted_v[-1],
            "mean": sum(values) / n,
            "p50": sorted_v[n // 2],
            "p95": sorted_v[int(n * 0.95)],
            "p99": sorted_v[int(n * 0.99)],
        }

    def reset(self):
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


class AnalyticsEngine:
    """Real-time analysis engine with threshold-based alerting"""

    def __init__(self, collector):
        self.collector = collector
        self._alerts = []
        self._thresholds = {}

    def set_threshold(self, metric_name, condition, value, severity="warning"):
        """Set an alert threshold: condition is 'gt','lt','gte','lte','eq'"""
        self._thresholds[metric_name] = {
            "condition": condition,
            "value": value,
            "severity": severity,
        }

    def analyze(self):
        """Run analysis and check all thresholds"""
        snapshot = self.collector.snapshot()
        alerts = []

        for metric_name, threshold in self._thresholds.items():
            metric_data = self.collector.get_metric(metric_name)
            if metric_data and metric_data:
                latest_value = metric_data[-1].value
                cond = threshold["condition"]
                thresh_val = threshold["value"]

                triggered = False
                if cond == "gt" and latest_value > thresh_val:
                    triggered = True
                elif cond == "lt" and latest_value < thresh_val:
                    triggered = True
                elif cond == "gte" and latest_value >= thresh_val:
                    triggered = True
                elif cond == "lte" and latest_value <= thresh_val:
                    triggered = True
                elif cond == "eq" and latest_value == thresh_val:
                    triggered = True

                if triggered:
                    alert = {
                        "metric": metric_name,
                        "value": latest_value,
                        "threshold": thresh_val,
                        "condition": cond,
                        "severity": threshold["severity"],
                        "timestamp": time.time(),
                    }
                    alerts.append(alert)
                    self._alerts.append(alert)

        return {
            "timestamp": time.time(),
            "snapshot": snapshot,
            "alerts": alerts,
            "threshold_count": len(self._thresholds),
        }

    def get_recent_alerts(self, limit=20):
        return self._alerts[-limit:]


class HealthMonitor:
    """System health monitoring with pluggable check functions"""

    def __init__(self):
        self._checks = {}
        self._status = {}
        self._history = deque(maxlen=1000)

    def register_check(self, name, check_fn, interval_sec=60.0):
        """Register a health check function"""
        self._checks[name] = {
            "fn": check_fn,
            "interval": interval_sec,
            "last_check": 0,
            "last_result": None,
        }

    def run_check(self, name):
        """Run a single health check by name"""
        if name not in self._checks:
            return None
        check = self._checks[name]
        try:
            if asyncio.iscoroutinefunction(check["fn"]):
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(check["fn"]())
                loop.close()
            else:
                result = check["fn"]()
            check["last_result"] = {"status": "healthy", "result": result}
        except Exception as e:
            check["last_result"] = {"status": "unhealthy", "error": str(e)}
        check["last_check"] = time.time()
        self._status[name] = check["last_result"]
        self._history.append({
            "check": name,
            "result": dict(check["last_result"]),
            "timestamp": time.time(),
        })
        return check["last_result"]

    def run_all(self):
        """Run all registered health checks"""
        results = {}
        for name in self._checks:
            results[name] = self.run_check(name)
        return results

    def get_status(self):
        """Get status of all registered checks"""
        status = {}
        for name, check in self._checks.items():
            last = check["last_result"] if check["last_result"] else {"status": "unknown"}
            status[name] = {
                "status": last.get("status"),
                "result": last.get("result"),
                "error": last.get("error"),
                "interval": check["interval"],
                "last_check": check["last_check"],
            }
        return status

    def is_healthy(self):
        """Check if all checks are healthy"""
        for name in self._checks:
            result = self._status.get(name)
            if not result or result.get("status") != "healthy":
                return False
        return True


class PerformanceTracker:
    """Performance span tracker for profiling code sections"""

    def __init__(self):
        self._spans = []
        self._active_spans = {}
        self._aggregations = {}

    def start_span(self, name, tags=None):
        """Start a performance span, returns span_id"""
        span_id = "span_{}_{}".format(time.time(), name)
        span = {
            "id": span_id, "name": name,
            "start": time.time(), "tags": tags or {},
            "children": [],
        }
        self._active_spans[span_id] = span
        return span_id

    def end_span(self, span_id, metadata=None):
        """End a performance span by ID"""
        if span_id not in self._active_spans:
            return
        span = self._active_spans.pop(span_id)
        span["end"] = time.time()
        span["duration_ms"] = (span["end"] - span["start"]) * 1000
        if metadata:
            span["metadata"] = metadata
        self._spans.append(span)

        name = span["name"]
        if name not in self._aggregations:
            self._aggregations[name] = {
                "count": 0, "total_ms": 0,
                "min_ms": float("inf"), "max_ms": 0,
            }
        agg = self._aggregations[name]
        agg["count"] += 1
        agg["total_ms"] += span["duration_ms"]
        agg["min_ms"] = min(agg["min_ms"], span["duration_ms"])
        agg["max_ms"] = max(agg["max_ms"], span["duration_ms"])

    def span(self, name):
        """Context manager for automatic span lifecycle"""
        return _SpanContext(self, name)

    def get_aggregations(self):
        """Get aggregated performance statistics"""
        result = {}
        for name, agg in self._aggregations.items():
            result[name] = {
                "count": agg["count"],
                "total_ms": agg["total_ms"],
                "min_ms": agg["min_ms"],
                "max_ms": agg["max_ms"],
                "avg_ms": agg["total_ms"] / agg["count"] if agg["count"] else 0,
            }
        return result

    def get_recent_spans(self, limit=50):
        return self._spans[-limit:]

    def reset(self):
        self._spans.clear()
        self._active_spans.clear()
        self._aggregations.clear()


class _SpanContext:
    """Context manager for automatic span lifecycle"""

    def __init__(self, tracker, name):
        self.tracker = tracker
        self.name = name
        self.span_id = None

    def __enter__(self):
        self.span_id = self.tracker.start_span(self.name)
        return self

    def __exit__(self, *args):
        self.tracker.end_span(self.span_id)


class UsageAnalytics:
    """Usage event tracking and reporting"""

    def __init__(self):
        self._events = deque(maxlen=50000)
        self._session_data = {}
        self._daily_stats = {}

    def track_event(self, event_type, user_id="anonymous", properties=None):
        """Track a usage event"""
        event = {
            "event_id": "evt_{}".format(time.time()),
            "type": event_type,
            "user_id": user_id,
            "properties": properties or {},
            "timestamp": time.time(),
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        self._events.append(event)

        date = event["date"]
        if date not in self._daily_stats:
            self._daily_stats[date] = {"events": 0, "unique_users": set()}
        self._daily_stats[date]["events"] += 1
        self._daily_stats[date]["unique_users"].add(user_id)

    def start_session(self, session_id, user_id="anonymous"):
        """Start tracking a session"""
        self._session_data[session_id] = {
            "user_id": user_id,
            "start": time.time(),
            "events": 0,
            "actions": [],
        }

    def end_session(self, session_id):
        """End session tracking"""
        if session_id in self._session_data:
            session = self._session_data.pop(session_id)
            session["end"] = time.time()
            session["duration_sec"] = session["end"] - session["start"]

    def get_daily_report(self, days=7):
        """Get daily usage report"""
        report = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            stats = self._daily_stats.get(date, {"events": 0, "unique_users": set()})
            report.append({
                "date": date,
                "events": stats["events"],
                "unique_users": len(stats["unique_users"]),
            })
        return report

    def get_event_summary(self):
        """Get event summary statistics"""
        event_types = defaultdict(int)
        for event in self._events:
            event_types[event["type"]] += 1
        return {
            "total_events": len(self._events),
            "by_type": dict(event_types),
            "date_range": {
                "start": self._events[0]["timestamp"] if self._events else None,
                "end": self._events[-1]["timestamp"] if self._events else None,
            },
        }