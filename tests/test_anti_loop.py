"""test_anti_loop.py — AntiLoopGuard regressions.

The LLM-calls-tool-in-a-loop footgun is the most expensive failure
mode in any MINXG release. These tests pin down that the guard
fires under three independent criteria.
"""
import pytest

from src.ai.safety.guard import (
    AntiLoopGuard,
    DepthGuard,
    DupDetector,
    CostGuard,
    get_guard,
    reset_guard,
)


def test_depth_guard_increments_and_resets():
    g = DepthGuard(max_depth=3)
    assert g.count == 0
    assert g.increment() == 1
    assert g.increment() == 2
    g.reset()
    assert g.count == 0


def test_dup_detector_rejects_repeat_within_window():
    d = DupDetector(window_size=2)
    args = {"x": 1}
    a1, _ = d.check("shell", args)
    assert a1
    a2, fp2 = d.check("shell", args)
    assert not a2
    assert fp2


def test_dup_detector_canonicalises_args():
    d = DupDetector(window_size=4)
    a1, _ = d.check("shell", {"a": 1, "b": 2})
    # Same keys, ordered differently — fingerprints must match.
    a2, _ = d.check("shell", {"b": 2, "a": 1})
    assert not a2


def test_dup_detector_window_eviction():
    """After window_size different calls, the original fingerprint
    is evicted and re-issued calls pass again."""
    d = DupDetector(window_size=2)
    d.check("a", {"x": 1})
    d.check("b", {"x": 2})
    d.check("c", {"x": 3})  # evicts "a"
    a, _ = d.check("a", {"x": 1})
    assert a, "evicted fingerprint should no longer block"


def test_cost_guard_caps_wall_clock():
    c = CostGuard(ceiling_ms=100)
    c.record(60)
    assert c.total_ms == 60
    c.record(50)
    assert c.total_ms == 110
    assert c.total_ms > c.ceiling_ms


def test_pre_check_depth_exceeded():
    g = AntiLoopGuard(max_depth=2, dedup_window=4, cost_ceiling_ms=10000)
    ok, why = g.pre_check("a", {})
    assert ok and why is None
    ok, why = g.pre_check("b", {})
    assert ok
    ok, why = g.pre_check("c", {})
    assert not ok and why == "depth_exceeded"


def test_pre_check_duplicate_calls_block():
    g = AntiLoopGuard(max_depth=8, dedup_window=2, cost_ceiling_ms=10000)
    ok1, _ = g.pre_check("a", {"x": 1})
    ok2, why2 = g.pre_check("a", {"x": 1})
    assert ok1 is True
    # second call is treated as a cached opportunity; orchestrator
    # may still proceed if it has the cached answer.
    assert not ok2 and why2 == "cached"


def test_pre_check_cost_exceeded_blocks():
    g = AntiLoopGuard(max_depth=10, dedup_window=10, cost_ceiling_ms=20)
    g.pre_check("a", {})  # 1
    g.record("a", {}, None, duration_ms=25)
    ok, why = g.pre_check("b", {})
    assert not ok and why == "cost_exceeded"


def test_record_never_raises_on_bad_args():
    g = AntiLoopGuard()
    # Non-dict args, odd duration — all must not raise.
    g.record("a", None, None, duration_ms=-5)
    g.record("a", object(), object(), duration_ms=float("inf"))
    assert g.snapshot()["depth"] == 0  # depth not bumped by record


def test_reset_clears_all_counters():
    g = AntiLoopGuard(max_depth=3, dedup_window=2, cost_ceiling_ms=50)
    g.pre_check("a", {})
    g.pre_check("a", {})
    g.record("a", {}, None, duration_ms=10)
    g.reset()
    snap = g.snapshot()
    assert snap["depth"] == 0
    assert snap["cost_ms"] == 0
    ok, _ = g.pre_check("a", {})
    assert ok, "post-reset the same call should pass again"


def test_get_context_injection_under_idle_guard():
    g = AntiLoopGuard(max_depth=8, dedup_window=4, cost_ceiling_ms=30000)
    assert g.get_context_injection() == ""  # nothing to say


def test_get_context_injection_after_loop():
    g = AntiLoopGuard(max_depth=5, dedup_window=4, cost_ceiling_ms=30000)
    for _ in range(4):
        g.pre_check("shell", {"cmd": "ls"})
        g.record("shell", {"cmd": "ls"}, {"out": "x"}, duration_ms=5)
    inj = g.get_context_injection()
    assert "[anti-loop]" in inj
    assert "deep into tool-call budget" in inj
    assert "repeated the same tool" in inj


def test_singleton_get_guard_then_reset():
    reset_guard()
    g1 = get_guard()
    g1.pre_check("singleton_probe", {})
    assert g1.depth_guard.count == 1
    g1.reset()
    assert g1.depth_guard.count == 0
    # Subsequent get_guard() returns the *same* singleton.
    g2 = get_guard()
    assert g1 is g2


def test_mobile_softens_ceiling():
    g = AntiLoopGuard(max_depth=20, dedup_window=10, cost_ceiling_ms=60000,
                      is_mobile=True)
    assert g.depth_guard.max_depth <= 5
    assert g.dup_detector.window_size <= 3
    assert g.cost_guard.ceiling_ms <= 12000
