#!/usr/bin/env python3
"""
MINXG Benchmark Script

Measures performance of various MINXG operations.
"""
import time
import sys
from pathlib import Path

def benchmark_import():
    """Benchmark module import time."""
    start = time.time()
    import minxg
    elapsed = (time.time() - start) * 1000
    return elapsed

def benchmark_memory_ops(iterations=1000):
    """Benchmark memory operations."""
    from multiligua_cli.memory_system import MemoryEngine
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = MemoryEngine(str(Path(tmpdir) / "bench.json"))

        # Add
        start = time.time()
        for i in range(iterations):
            engine.add(f"Test memory {i}", importance=0.5)
        add_time = (time.time() - start) * 1000

        # Search
        start = time.time()
        for i in range(100):
            engine.search(f"memory {i % 10}")
        search_time = (time.time() - start) * 1000

        # Stats
        start = time.time()
        for i in range(10):
            engine.get_stats()
        stats_time = (time.time() - start) * 1000

        return {
            "add_time_ms": add_time,
            "add_per_sec": iterations / (add_time / 1000),
            "search_time_ms": search_time,
            "stats_time_ms": stats_time,
        }

def benchmark_cost_tracker(iterations=10000):
    """Benchmark cost tracker."""
    from multiligua_cli.cost_tracker import CostTracker

    tracker = CostTracker()

    start = time.time()
    for i in range(iterations):
        tracker.record("openai", "gpt-4o", 100, 50, latency_ms=200)
    elapsed = (time.time() - start) * 1000

    return {
        "record_time_ms": elapsed,
        "records_per_sec": iterations / (elapsed / 1000),
        "total_cost": tracker.total_cost,
    }

def benchmark_themes():
    """Benchmark theme switching."""
    from multiligua_cli.themes import set_theme, get_theme

    themes = ["blue-premium", "dark-modern", "matrix", "warm-sunset"]

    start = time.time()
    for i in range(100):
        set_theme(themes[i % len(themes)])
    elapsed = (time.time() - start) * 1000

    return {
        "switch_time_ms": elapsed,
        "switches_per_sec": 100 / (elapsed / 1000),
    }

def main():
    print("=" * 60)
    print("  MINXG Benchmark Suite")
    print("=" * 60)

    # Import benchmark
    import_time = benchmark_import()
    print(f"\n[Import] Module import: {import_time:.2f}ms")

    # Memory benchmark
    print("\n[Memory Operations] (1000 iterations)")
    mem_results = benchmark_memory_ops(1000)
    print(f"  Add: {mem_results['add_time_ms']:.2f}ms ({mem_results['add_per_sec']:.0f}/sec)")
    print(f"  Search: {mem_results['search_time_ms']:.2f}ms")
    print(f"  Stats: {mem_results['stats_time_ms']:.2f}ms")

    # Cost tracker benchmark
    print("\n[Cost Tracker] (10000 iterations)")
    cost_results = benchmark_cost_tracker(10000)
    print(f"  Record: {cost_results['record_time_ms']:.2f}ms ({cost_results['records_per_sec']:.0f}/sec)")
    print(f"  Total cost tracked: ${cost_results['total_cost']:.4f}")

    # Theme benchmark
    print("\n[Theme System]")
    theme_results = benchmark_themes()
    print(f"  Switch: {theme_results['switch_time_ms']:.2f}ms ({theme_results['switches_per_sec']:.0f}/sec)")

    print("\n" + "=" * 60)
    print("  Benchmark complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
