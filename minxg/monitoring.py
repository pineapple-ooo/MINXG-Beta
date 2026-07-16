"""
MINXG Monitoring — Real-time observability and metrics.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import time
import json
from collections import defaultdict
from pathlib import Path


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Collect and aggregate metrics.

    Supports counters, gauges, histograms, and summaries.
    """

    def __init__(self):
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.history: Dict[str, List[MetricPoint]] = defaultdict(list)
        self.max_history = 10000

    def inc(self, name: str, value: float = 1, labels: Optional[Dict] = None) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        self.counters[key] += value
        self._record(name, value, labels)

    def set(self, name: str, value: float, labels: Optional[Dict] = None) -> None:
        """Set a gauge."""
        key = self._make_key(name, labels)
        self.gauges[key] = value
        self._record(name, value, labels)

    def observe(self, name: str, value: float, labels: Optional[Dict] = None) -> None:
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
        self._record(name, value, labels)

    def get(self, name: str, labels: Optional[Dict] = None) -> float:
        """Get current metric value."""
        key = self._make_key(name, labels)
        if key in self.counters:
            return self.counters[key]
        if key in self.gauges:
            return self.gauges[key]
        return 0

    def get_histogram(self, name: str, labels: Optional[Dict] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self.histograms.get(key, [])
        if not values:
            return {}

        values.sort()
        return {
            "count": len(values),
            "sum": sum(values),
            "mean": sum(values) / len(values),
            "min": values[0],
            "max": values[-1],
            "p50": values[int(len(values) * 0.5)],
            "p90": values[int(len(values) * 0.9)],
            "p99": values[int(len(values) * 0.99)],
        }

    def get_all(self) -> Dict[str, Any]:
        """Get all metrics."""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: self.get_histogram(k) for k in self.histograms},
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.history.clear()

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        for key, value in self.counters.items():
            lines.append(f"{key} {value}")
        for key, value in self.gauges.items():
            lines.append(f"{key} {value}")
        return "\n".join(lines)

    def _make_key(self, name: str, labels: Optional[Dict] = None) -> str:
        """Create metric key from name and labels."""
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def _record(self, name: str, value: float, labels: Optional[Dict] = None) -> None:
        """Record to history."""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {},
        )
        self.history[name].append(point)
        if len(self.history[name]) > self.max_history:
            self.history[name] = self.history[name][-self.max_history:]


class RequestTracker:
    """Track API request metrics."""

    def __init__(self):
        self.metrics = MetricsCollector()
        self.active_requests = 0

    def start_request(self, endpoint: str, method: str = "POST") -> "RequestTimer":
        """Start tracking a request."""
        self.active_requests += 1
        self.metrics.inc("requests_total", labels={"endpoint": endpoint, "method": method})
        return RequestTimer(self, endpoint, method)

    def record_latency(self, endpoint: str, latency_ms: float) -> None:
        """Record request latency."""
        self.metrics.observe("request_latency_ms", latency_ms, labels={"endpoint": endpoint})

    def record_error(self, endpoint: str, error_type: str) -> None:
        """Record request error."""
        self.metrics.inc("errors_total", labels={"endpoint": endpoint, "type": error_type})

    def record_tokens(self, tokens: int, model: str) -> None:
        """Record token usage."""
        self.metrics.inc("tokens_total", tokens, labels={"model": model})
        self.metrics.set("tokens_per_request", tokens, labels={"model": model})

    def record_cost(self, cost: float, model: str) -> None:
        """Record API cost."""
        self.metrics.inc("cost_total_usd", cost, labels={"model": model})

    def get_dashboard(self) -> Dict[str, Any]:
        """Get monitoring dashboard data."""
        return {
            "active_requests": self.active_requests,
            "requests_total": self.metrics.get("requests_total"),
            "errors_total": self.metrics.get("errors_total"),
            "tokens_total": self.metrics.get("tokens_total"),
            "cost_total_usd": self.metrics.get("cost_total_usd"),
            "latency_p50": self.metrics.get_histogram("request_latency_ms").get("p50", 0),
            "latency_p99": self.metrics.get_histogram("request_latency_ms").get("p99", 0),
            "avg_latency": self.metrics.get_histogram("request_latency_ms").get("mean", 0),
        }


class RequestTimer:
    """Context manager for timing requests."""

    def __init__(self, tracker: RequestTracker, endpoint: str, method: str):
        self.tracker = tracker
        self.endpoint = endpoint
        self.method = method
        self.start_time = time.time()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tracker.active_requests -= 1
        latency_ms = (time.time() - self.start_time) * 1000
        self.tracker.record_latency(self.endpoint, latency_ms)
        if exc_type:
            self.tracker.record_error(self.endpoint, exc_type.__name__)
        return False


class AlertManager:
    """Manage alerts and notifications."""

    def __init__(self):
        self.rules: List[Dict] = []
        self.alerts: List[Dict] = []
        self.webhooks: List[str] = []

    def add_rule(
        self,
        name: str,
        condition: str,
        severity: str = "warning",
        message: str = "",
    ) -> None:
        """Add an alert rule."""
        self.rules.append({
            "name": name,
            "condition": condition,
            "severity": severity,
            "message": message,
        })

    def evaluate(self, metrics: Dict[str, float]) -> List[Dict]:
        """Evaluate alert rules against current metrics."""
        triggered = []
        for rule in self.rules:
            try:
                if eval(rule["condition"], {"__builtins__": {}}, metrics):
                    alert = {
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "timestamp": time.time(),
                        "values": metrics,
                    }
                    triggered.append(alert)
                    self.alerts.append(alert)
            except Exception:
                pass
        return triggered

    def add_webhook(self, url: str) -> None:
        """Add a webhook URL for alert notifications."""
        self.webhooks.append(url)

    def send_alerts(self, alerts: List[Dict]) -> Dict[str, int]:
        """Send alerts to webhooks."""
        sent = 0
        failed = 0
        for url in self.webhooks:
            try:
                import requests
                for alert in alerts:
                    requests.post(url, json=alert, timeout=10)
                    sent += 1
            except Exception:
                failed += 1
        return {"sent": sent, "failed": failed}

    def get_alerts(self, last_n: int = 100) -> List[Dict]:
        """Get recent alerts."""
        return self.alerts[-last_n:]


class HealthChecker:
    """System health monitoring."""

    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self.results: Dict[str, Dict] = {}

    def register(self, name: str, check: callable) -> None:
        """Register a health check."""
        self.checks[name] = check

    def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_healthy = True

        for name, check in self.checks.items():
            try:
                result = check()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "healthy": result,
                    "checked_at": time.time(),
                }
                if not result:
                    overall_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "healthy": False,
                    "error": str(e),
                    "checked_at": time.time(),
                }
                overall_healthy = False

        self.results = results
        return {
            "healthy": overall_healthy,
            "checks": results,
            "timestamp": time.time(),
        }

    def get_status(self) -> str:
        """Get overall health status."""
        if not self.results:
            self.check_all()

        all_healthy = all(r.get("healthy", False) for r in self.results.values())
        return "healthy" if all_healthy else "unhealthy"


# Default instances
_default_tracker = RequestTracker()
_default_alerts = AlertManager()
_default_health = HealthChecker()


def get_tracker() -> RequestTracker:
    """Get default request tracker."""
    return _default_tracker


def get_alerts() -> AlertManager:
    """Get default alert manager."""
    return _default_alerts


def get_health() -> HealthChecker:
    """Get default health checker."""
    return _default_health
