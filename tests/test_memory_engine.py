"""test_memory_engine.py — entropic memory engine + working buffer."""
import sys
import tempfile

import pytest

from src.ai.memory.entropic_evolution import (
    EntropicEvolutionEngine,
    L0HotStore,
    L1WarmStore,
    MemoryItem,
    get_entropic_engine,
    reset_engine_for_tests,
)
from src.ai.memory.working_memory import (
    WorkingMemory,
    get_working_memory,
    reset_working_memory_for_tests,
)


def _make_item(text, *, role="user", ts=0.0, pinned=False, tags=("test",)):
    """Helper that builds a MemoryItem with a fresh id and a real vector."""
    import hashlib
    from src.ai.memory.entropic_evolution import _vectorise
    return MemoryItem(
        item_id=hashlib.sha1(text.encode("utf-8")).hexdigest()[:16],
        role=role, text=text, created_at=ts,
        vector=_vectorise(text, 64),
        tags=tags,
        pinned=pinned,
    )


def test_l0_caps_at_capacity():
    s = L0HotStore(capacity=4)
    for i in range(10):
        s.add(_make_item(f"text-{i}", role="user"))
    snap = s.query(n=100)
    assert len(snap) == 4


def test_l1_retrieval_returns_relevant_first():
    s = L1WarmStore(dim=64, max_items=200)
    s.add(_make_item("the cat sat on the mat", ts=1.0))
    s.add(_make_item("pythagorean theorem about triangles", ts=2.0))
    s.add(_make_item("how to train a neural network", ts=3.0))
    out = s.query("tell me about the mathematical theorem", k=3)
    assert out, "expected at least one hit"
    top_text = out[0].text
    assert "pythagorean" in top_text or "theorem" in top_text


def test_l1_cap_eviction_keeps_pinned():
    s = L1WarmStore(dim=64, max_items=4)
    s.add(_make_item("keep me 1", ts=1.0, pinned=True))
    s.add(_make_item("temp 2", ts=2.0))
    s.add(_make_item("temp 3", ts=3.0))
    s.add(_make_item("temp 4", ts=4.0))
    s.add(_make_item("temp 5", ts=5.0))
    texts = {m.text for m in s._items}
    assert "keep me 1" in texts, "pinned must survive"


def test_engine_records_three_tiers_on_exchange(tmp_path):
    db = tmp_path / "mem.sqlite"
    eng = EntropicEvolutionEngine(l0_capacity=8, l1_max_items=32,
                                   l2_db_path=str(db),
                                   vector_dim=64)
    out = eng.learn_from_exchange(
        "remember the project name is Acme",
        "Got it, Acme project.",
        tool_calls=["shell", "fetch_url"],
    )
    assert out["behaviors_learned"] >= 3
    snap_l0 = eng.l0.query(n=8)
    assert any("Acme" in m.text for m in snap_l0)


def test_engine_get_memory_context_returns_recent_first(tmp_path):
    db = tmp_path / "mem.sqlite"
    eng = EntropicEvolutionEngine(l0_capacity=4, l1_max_items=16,
                                   l2_db_path=str(db),
                                   vector_dim=64)
    eng.learn_from_user_message("first about Acme and entropy")
    eng.learn_from_user_message("second about trees and branches")
    eng.learn_from_user_message("third about entropy again please")
    ctx = eng.get_memory_context(max_items=6)
    assert "third" in ctx


def test_engine_persistence_round_trip(tmp_path):
    db = tmp_path / "mem.sqlite"
    eng1 = EntropicEvolutionEngine(l1_max_items=8, l2_db_path=str(db))
    eng1.learn_from_user_message("remember alpha project")
    eng1.learn_from_user_message("remember beta experiment")
    eng2 = EntropicEvolutionEngine(l1_max_items=8, l2_db_path=str(db))
    ctx = eng2.get_memory_context(max_items=4)
    assert ctx, "cold-start fresh engine should reload from cold layer"


def test_engine_singleton_resets():
    reset_engine_for_tests()
    e1 = get_entropic_engine()
    e2 = get_entropic_engine()
    assert e1 is e2
    reset_engine_for_tests()
    e3 = get_entropic_engine()
    assert e3 is not e1


# ───────────────────────────────────── working memory ────────


def test_working_memory_keeps_turns_in_order():
    w = WorkingMemory(capacity=4)
    w.prime("hello", role="user")
    w.prime("hi, what's up?", role="assistant")
    w.prime("building minxg", role="user")
    snap = w.snapshot()
    roles = [t["role"] for t in snap["turns"]]
    assert roles == ["user", "assistant", "user"]


def test_working_memory_push_tool_records_result():
    w = WorkingMemory(capacity=4)
    w.mark_tool_call_started("shell", {"cmd": "ls"})
    w.push_tool("shell", {"cmd": "ls"}, {"out": "a\nb"})
    snap = w.snapshot()
    assert any(t["role"] == "tool" for t in snap["turns"])
    assert snap["pending_tools"], "pending tool should persist until cleared"


def test_working_memory_serialised_for_prompt_includes_recent():
    w = WorkingMemory(capacity=8)
    w.prime("first")
    w.prime("second")
    w.prime("third")
    flat = w.serialised_for_prompt()
    assert "first" in flat and "second" in flat and "third" in flat


def test_working_memory_singleton():
    reset_working_memory_for_tests()
    a = get_working_memory()
    b = get_working_memory()
    assert a is b
    reset_working_memory_for_tests()
    c = get_working_memory()
    assert c is not a
