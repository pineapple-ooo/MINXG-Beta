"""
"""
from __future__ import annotations
from typing import Dict, List
import time
import math
from minxg.base import BaseWorker, tool


class BenchmarkToolsWorker(BaseWorker):
    facade_alias = "data_tools"
    worker_id = "benchmark_tools"
    version = "0.17.0"

    @tool(description="Measure code execution time", category="measure")
    async def estimate_latency(self, operation: str, data_size: int = 1000) -> Dict:
        estimates = {
            "file_read": 0.5, "file_write": 1.0, "network_rtt": 50.0,
            "db_query": 5.0, "hash_sha256": 0.01, "json_parse": 0.1,
            "regex_match": 0.05, "sort_1k": 0.3,
        }
        base = estimates.get(operation, 1.0)
        scaled = base * (data_size / 1000) if operation in ("sort_1k", "json_parse") else base
        return {"operation": operation, "data_size": data_size, "estimated_ms": round(scaled, 4),
                "note": "rough estimates, not actual measurements"}

    @tool(description="Calculate transfer time", category="calc")
    async def transfer_time(self, size_bytes: int, bandwidth_mbps: float = 100.0) -> Dict:
        bits = size_bytes * 8
        bps = bandwidth_mbps * 1_000_000
        seconds = bits / bps if bps else 0
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        return {"size_bytes": size_bytes, "bandwidth_mbps": bandwidth_mbps,
                "seconds": round(seconds, 4),
                "formatted": f"{int(h)}h {int(m)}m {s:.1f}s" if h else f"{int(m)}m {s:.1f}s"}

    @tool(description="Generate benchmark report template", category="report")
    async def benchmark_report(self, name: str, measurements: dict) -> Dict:
        lines = [f"# Benchmark: {name}", f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        lines.append("| Metric | Value | Unit |")
        lines.append("|--------|-------|------|")
        for k, v in measurements.items():
            lines.append(f"| {k} | {v[0] if isinstance(v, list) else v} | {v[1] if isinstance(v, list) else 'N/A'} |")
        stats = {}
        for k, v in measurements.items():
            val = v[0] if isinstance(v, list) else v
            if isinstance(val, (int, float)):
                stats[k] = val
        if stats:
            lines.append(f"\n- **Min:** {min(stats.values())}")
            lines.append(f"- **Max:** {max(stats.values())}")
            lines.append(f"- **Avg:** {round(sum(stats.values())/len(stats), 2)}")
        return {"report": "\n".join(lines), "measurements": len(measurements)}

    @tool(description="Calculate QPS", category="calc")
    async def calc_qps(self, total_requests: int, duration_seconds: float) -> Dict:
        qps = total_requests / duration_seconds if duration_seconds else 0
        return {"total_requests": total_requests, "duration_seconds": duration_seconds,
                "qps": round(qps, 2), "avg_latency_ms": round(1000 / qps, 2) if qps else 0}

    @tool(description="Calculate P50/P95/P99 latency", category="calc")
    async def percentile_latency(self, latencies: list) -> Dict:
        if not latencies:
            return {"error": "empty list"}
        nums = sorted(float(x) for x in latencies if isinstance(x, (int, float)) or str(x).replace(".","").isdigit())
        if not nums:
            return {"error": "no valid numbers"}
        n = len(nums)
        def _p(pct):
            idx = int(n * pct / 100)
            return nums[min(idx, n - 1)]
        return {
            "count": n, "min": nums[0], "max": nums[-1],
            "avg": round(sum(nums) / n, 2),
            "p50": _p(50), "p90": _p(90), "p95": _p(95), "p99": _p(99),
        }

    @tool(description="Estimate memory usage", category="calc")
    async def estimate_memory(self, data_type: str, count: int) -> Dict:
        sizes = {"int": 28, "float": 24, "str_10": 59, "str_100": 149,
                 "dict_entry": 72, "list_item": 8, "bool": 28, "bytes_1k": 1033}
        per_item = sizes.get(data_type, 50)
        total = per_item * count
        return {"data_type": data_type, "count": count, "estimated_bytes": total,
                "estimated_kb": round(total / 1024, 2), "estimated_mb": round(total / (1024*1024), 4)}

    @tool(description="Estimate API throughput bottleneck", category="calc")
    async def throughput_bottleneck(self, requests_per_sec: float, avg_processing_ms: float,
                                     concurrency: int = 10) -> Dict:
        capacity = concurrency / (avg_processing_ms / 1000) if avg_processing_ms else 0
        headroom = capacity - requests_per_sec
        status = "healthy" if headroom > requests_per_sec * 0.5 else ("warning" if headroom > 0 else "overloaded")
        return {"capacity_rps": round(capacity, 2), "current_rps": requests_per_sec,
                "headroom_rps": round(headroom, 2), "status": status,
                "recommendation": "scale up" if status == "overloaded" else "ok"}

    @tool(description="Calculate cache hit rate benefit", category="calc")
    async def cache_benefit(self, hit_rate: float, miss_latency_ms: float,
                             hit_latency_ms: float = 1.0) -> Dict:
        avg_no_cache = miss_latency_ms
        avg_with_cache = hit_rate * hit_latency_ms + (1 - hit_rate) * miss_latency_ms
        speedup = avg_no_cache / avg_with_cache if avg_with_cache else 1
        return {"hit_rate": hit_rate, "avg_latency_no_cache_ms": avg_no_cache,
                "avg_latency_with_cache_ms": round(avg_with_cache, 2),
                "speedup": f"{speedup:.1f}x", "savings_pct": round((1 - avg_with_cache/avg_no_cache)*100, 1)}

    @tool(description="Calculate service availability", category="calc")
    async def availability(self, uptime_hours: float, downtime_minutes: float) -> Dict:
        total = uptime_hours * 60 + downtime_minutes
        avail = (uptime_hours * 60) / total * 100 if total else 100
        nines = round(-math.log10(1 - avail / 100), 2) if avail < 100 else float('inf')
        return {"uptime_hours": uptime_hours, "downtime_minutes": downtime_minutes,
                "availability_pct": round(avail, 4), "nines": nines}

    @tool(description="Calculate database index efficiency", category="calc")
    async def index_estimation(self, row_count: int, page_size: int = 4096, key_size: int = 16) -> Dict:
        keys_per_page = page_size // (key_size + 8)
        tree_height = math.ceil(math.log(row_count, keys_per_page)) if row_count > 1 else 1
        io_cost = tree_height
        seq_scan_io = math.ceil(row_count * 200 / page_size)
        return {"row_count": row_count, "b_tree_height": tree_height,
                "index_lookup_io": io_cost, "seq_scan_io": seq_scan_io,
                "improvement": f"{seq_scan_io // io_cost}x" if io_cost else "N/A"}
