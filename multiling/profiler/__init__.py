"""
profiler.py - Performance Profiling Tools

Provides:
  - CodeProfiler: Line-level and function-level profiling
  - MemoryProfiler: Memory usage tracking
  - TimingProfiler: Detailed timing analysis
  - ProfileReport: HTML/text profiling reports
"""

import asyncio
import cProfile
import functools
import io
import linecache
import os
import pstats
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ProfileEntry:
    """Single profile measurement"""
    func_name: str
    file: str
    line: int
    calls: int
    total_time: float
    cumtime: float
    percall: float
    subcalls: int = 0

    def to_dict(self) -> dict:
        return {
            "func": self.func_name,
            "file": "{}:{}".format(self.file, self.line),
            "calls": self.calls,
            "total_ms": round(self.total_time * 1000, 3),
            "cumtime_ms": round(self.cumtime * 1000, 3),
            "percall_ms": round(self.percall * 1000, 3),
        }


@dataclass
class MemorySnapshot:
    """Memory usage snapshot"""
    timestamp: float = field(default_factory=time.time)
    rss_bytes: int = 0
    heap_objects: int = 0
    top_allocations: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "rss_mb": round(self.rss_bytes / 1024 / 1024, 2),
            "heap_objects": self.heap_objects,
            "top_allocations": self.top_allocations[:10],
        }


class CodeProfiler:
    """CPU and call-count profiler"""

    def __init__(self):
        self._profiler = cProfile.Profile()
        self._active = False
        self._snapshots: List[ProfileEntry] = []

    def start(self):
        """Start profiling"""
        self._profiler.enable()
        self._active = True

    def stop(self):
        """Stop profiling"""
        self._profiler.disable()
        self._active = False

    def snapshot(self) -> List[ProfileEntry]:
        """Get current profile snapshot"""
        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.strip_dirs().sort_stats("cumulative")
        stats.calc_callees()

        entries = []
        for func, (cc, nc, tt, ct, callers) in stats.stats.items():
            filename, line, name = func
            entries.append(ProfileEntry(
                func_name=name,
                file=filename,
                line=line,
                calls=nc,
                total_time=tt,
                cumtime=ct,
                percall=tt / nc if nc > 0 else 0,
                subcalls=cc,
            ))

        entries.sort(key=lambda e: e.cumtime, reverse=True)
        self._snapshots = entries
        return entries[:50]

    def get_report(self, limit: int = 20, sort: str = "cumtime") -> str:
        """Generate text profiling report"""
        entries = self.snapshot()

        lines = []
        lines.append("=" * 80)
        lines.append("CODE PROFILING REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Sort entries
        if sort == "cumtime":
            entries.sort(key=lambda e: e.cumtime, reverse=True)
        elif sort == "tottime":
            entries.sort(key=lambda e: e.total_time, reverse=True)
        elif sort == "calls":
            entries.sort(key=lambda e: e.calls, reverse=True)

        lines.append("{:<40} {:>10} {:>12} {:>12} {:>8}".format(
            "Function", "Calls", "CumTime(ms)", "TotTime(ms)", "File:Line"
        ))
        lines.append("-" * 80)

        for e in entries[:limit]:
            loc = "{}:{}".format(
                os.path.basename(e.file), e.line
            )
            lines.append("{:<40} {:>10} {:>12.2f} {:>12.2f} {:>8}".format(
                e.func_name[:40],
                e.calls,
                e.cumtime * 1000,
                e.total_time * 1000,
                loc,
            ))

        lines.append("-" * 80)
        return "\n".join(lines)

    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile a function"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.start()
            try:
                return func(*args, **kwargs)
            finally:
                self.stop()
        return wrapper

    def profile_async(self, func: Callable) -> Callable:
        """Decorator to profile an async function"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            self.start()
            try:
                return await func(*args, **kwargs)
            finally:
                self.stop()
        return wrapper

    def reset(self):
        self._profiler.clear()
        self._snapshots.clear()


class MemoryProfiler:
    """Memory usage profiler"""

    def __init__(self):
        self._snapshots: List[MemorySnapshot] = []
        self._tracking = False

    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot"""
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        except Exception:
            rss = 0

        try:
            import gc
            gc.collect()
            heap_count = len(gc.get_objects())
        except Exception:
            heap_count = 0

        snap = MemorySnapshot(
            rss_bytes=rss,
            heap_objects=heap_count,
        )
        self._snapshots.append(snap)
        return snap

    def get_trend(self) -> Dict:
        """Get memory usage trend"""
        if len(self._snapshots) < 2:
            return {"snapshots": len(self._snapshots)}

        first = self._snapshots[0].rss_bytes
        last = self._snapshots[-1].rss_bytes
        peak = max(s.rss_bytes for s in self._snapshots)

        return {
            "start_mb": round(first / 1024 / 1024, 2),
            "current_mb": round(last / 1024 / 1024, 2),
            "peak_mb": round(peak / 1024 / 1024, 2),
            "growth_mb": round((last - first) / 1024 / 1024, 2),
            "snapshots": len(self._snapshots),
        }

    def track(self, func: Callable) -> Callable:
        """Decorator to track memory around function call"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            before = self.take_snapshot()
            try:
                result = func(*args, **kwargs)
            finally:
                after = self.take_snapshot()
            return result
        return wrapper

    def get_report(self) -> str:
        """Generate memory profiling report"""
        trend = self.get_trend()
        lines = [
            "=" * 50,
            "MEMORY PROFILING REPORT",
            "=" * 50,
            "Snapshots: {}".format(trend.get("snapshots", 0)),
        ]
        if trend.get("start_mb") is not None:
            lines.extend([
                "Start: {} MB".format(trend["start_mb"]),
                "Current: {} MB".format(trend["current_mb"]),
                "Peak: {} MB".format(trend["peak_mb"]),
                "Growth: {} MB".format(trend["growth_mb"]),
            ])
        return "\n".join(lines)


class TimingProfiler:
    """Detailed timing profiler for code sections"""

    def __init__(self):
        self._timings: Dict[str, List[float]] = defaultdict(list)

    def time(self, label: str) -> "TimingProfiler":
        """Context manager for timing a code section"""
        return _TimingContext(self, label)

    def record(self, label: str, duration_ms: float):
        """Manually record a timing"""
        self._timings[label].append(duration_ms)

    def time_function(self, func: Callable) -> Callable:
        """Decorator to time function execution"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            self.record(func.__name__, elapsed)
            return result
        return wrapper

    def time_async(self, func: Callable) -> Callable:
        """Decorator to time async function execution"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            self.record(func.__name__, elapsed)
            return result
        return wrapper

    def get_stats(self, label: str = None) -> Dict:
        """Get timing statistics"""
        if label:
            return self._compute_stats(label, self._timings.get(label, []))
        return {k: self._compute_stats(k, v) for k, v in self._timings.items()}

    def _compute_stats(self, label: str, timings: List[float]) -> Dict:
        if not timings:
            return {"label": label, "count": 0}
        sorted_t = sorted(timings)
        n = len(sorted_t)
        return {
            "label": label,
            "count": n,
            "min_ms": round(sorted_t[0], 3),
            "max_ms": round(sorted_t[-1], 3),
            "mean_ms": round(sum(timings) / n, 3),
            "median_ms": round(sorted_t[n // 2], 3),
            "p95_ms": round(sorted_t[int(n * 0.95)], 3) if n > 1 else sorted_t[0],
            "p99_ms": round(sorted_t[int(n * 0.99)], 3) if n > 1 else sorted_t[0],
            "total_ms": round(sum(timings), 3),
        }

    def reset(self):
        self._timings.clear()


class _TimingContext:
    """Timing context manager"""

    def __init__(self, profiler: TimingProfiler, label: str):
        self.profiler = profiler
        self.label = label
        self.start = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = (time.perf_counter() - self.start) * 1000
        self.profiler.record(self.label, elapsed)


class ProfileReport:
    """Generate profiling reports"""

    def __init__(self, code_profiler: CodeProfiler = None,
                 mem_profiler: MemoryProfiler = None,
                 timing_profiler: TimingProfiler = None):
        self.code = code_profiler
        self.memory = mem_profiler
        self.timing = timing_profiler

    def generate_text_report(self) -> str:
        """Generate comprehensive text report"""
        lines = ["=" * 80, "PROFILE REPORT", "=" * 80, ""]

        if self.memory:
            lines.append(self.memory.get_report())
            lines.append("")

        if self.code:
            lines.append(self.code.get_report())
            lines.append("")

        if self.timing:
            stats = self.timing.get_stats()
            if stats:
                lines.append("TIMING STATISTICS")
                lines.append("-" * 60)
                for label, data in sorted(stats.items(),
                                         key=lambda x: x[1].get("total_ms", 0),
                                         reverse=True):
                    if data.get("count", 0) > 0:
                        lines.append(
                            "  {:<30} calls={:<6} mean={:<10.2f}ms "
                            "p95={:<10.2f}ms total={:<10.2f}ms".format(
                                label[:30], data["count"],
                                data["mean_ms"], data["p95_ms"],
                                data["total_ms"],
                            )
                        )
                lines.append("")

        return "\n".join(lines)

    def generate_html_report(self) -> str:
        """Generate basic HTML profiling report"""
        parts = [
            "<html><head><title>Profile Report</title>",
            "<style>body{font-family:monospace;margin:20px;} "
            "table{border-collapse:collapse;width:100%;} "
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;} "
            "th{background:#4CAF50;color:white;}</style></head>",
            "<body><h1>Profile Report</h1>",
        ]

        if self.timing:
            stats = self.timing.get_stats()
            if stats:
                parts.append("<h2>Timing Statistics</h2><table>")
                parts.append("<tr><th>Function</th><th>Calls</th>"
                             "<th>Mean(ms)</th><th>P95(ms)</th>"
                             "<th>Total(ms)</th></tr>")
                for label, data in sorted(stats.items(),
                                         key=lambda x: x[1].get("total_ms", 0),
                                         reverse=True):
                    if data.get("count", 0) > 0:
                        parts.append(
                            "<tr><td>{}</td><td>{}</td><td>{:.3f}</td>"
                            "<td>{:.3f}</td><td>{:.3f}</td></tr>".format(
                                label, data["count"], data["mean_ms"],
                                data["p95_ms"], data["total_ms"],
                            )
                        )
                parts.append("</table>")

        if self.memory:
            trend = self.memory.get_trend()
            parts.append("<h2>Memory Usage</h2><ul>")
            for k, v in trend.items():
                parts.append("<li>{}: {}</li>".format(k, v))
            parts.append("</ul>")

        parts.append("</body></html>")
        return "\n".join(parts)