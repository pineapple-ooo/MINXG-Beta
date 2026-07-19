"""tests/test_self_evolution.py -- SelfEvolutionWorker tests."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.self_evolution import SelfEvolutionWorker
from minxg.base import BaseWorker


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture
def w():
    return SelfEvolutionWorker()


def test_subclass(w):
    assert issubclass(SelfEvolutionWorker, BaseWorker)


def test_worker_id(w):
    assert w.worker_id == "evolution_tools"


def test_tier(w):
    assert w.tier == "ai"


def test_record_and_recall(w):
    """Record a lesson then recall it (v2: dedup-aware so accepts both
    'recorded' and 'merged' actions)."""
    # Record (will be 'merged' if the global log already has this lesson,
    # 'recorded' on fresh logs)
    r = _run(w.evolution_record(
        task="__unique_test_marker__ fix gateway startup",
        approach="__unique_approach_marker__ traced _pick_initial_mode fallback",
        tools_used=["grep", "pytest"],
        outcome="success",
        lessons=["__unique_test_marker__ gateway sub_command None means status not start"],
        cost_seconds=120,
    ))
    assert r["status"] == "ok"
    # Either recorded (fresh) or merged (re-run) is fine
    assert "recorded_id" in r or "merged_into" in r

    # Recall
    r2 = _run(w.evolution_recall("__unique_test_marker__ gateway startup"))
    assert r2["status"] == "ok"
    assert r2["total_records"] >= 1
    # Our record should be in the results
    found = any("__unique_test_marker__" in str(res.get("task", ""))
                 for res in r2.get("results", []))
    assert found, "recorded lesson not recalled"


def test_recall_empty(w):
    """Recall should work even with no matching records."""
    r = _run(w.evolution_recall(
        "quantum entanglement simulation"))
    assert r["status"] == "ok"


def test_stats(w):
    r = _run(w.evolution_stats())
    assert r["status"] == "ok"
    assert "total_records" in r


def test_clear_without_confirm(w):
    r = _run(w.evolution_clear(confirm=False))
    assert r["status"] == "error"


def test_clear_with_confirm(w):
    r = _run(w.evolution_clear(confirm=True))
    assert r["status"] == "ok"


def test_record_has_checksum(w):
    """v2: every record carries a SHA-256 checksum."""
    r = _run(w.evolution_record(
        task="checksum verification test",
        approach="write a record and inspect its checksum",
        tools_used=["pytest"],
        outcome="success",
        lessons=["records should have sha256 checksums"],
        cost_seconds=5,
    ))
    assert r["status"] == "ok"
    # Read the file directly
    from minxg.five_pillars.devtools.self_evolution import _evolution_path, _verify_checksum
    import json as _json
    lines = _evolution_path().read_text(encoding="utf-8").strip().split("\n")
    last = _json.loads(lines[-1])
    assert last.get("checksum", "").startswith("sha256:")
    assert _verify_checksum(last) is True


def test_record_schema_version(w):
    """v2: records are tagged with schema_version=2."""
    r = _run(w.evolution_record(
        task="schema version test",
        approach="write a record and check schema_version",
        tools_used=["pytest"],
        outcome="success",
        lessons=["v2 records carry schema_version=2"],
        cost_seconds=3,
    ))
    assert r["status"] == "ok"
    from minxg.five_pillars.devtools.self_evolution import _evolution_path
    import json as _json
    lines = _evolution_path().read_text(encoding="utf-8").strip().split("\n")
    last = _json.loads(lines[-1])
    assert last.get("schema_version") == 2


def test_dedup_merges_similar_records(w):
    """v2: recording a very similar task merges lessons instead of duplicating."""
    # Use unique markers so we don't collide with prior records in the
    # global evolution log from other tests.
    unique = "__dedup_test_marker__"
    r1 = _run(w.evolution_record(
        task=f"{unique} fix edge cache bug",
        approach=f"{unique} traced cache key fallback path",
        tools_used=["grep"],
        outcome="success",
        lessons=[f"{unique} lesson A from first recording"],
    ))
    assert r1["status"] == "ok"
    assert r1["action"] == "recorded"

    r2 = _run(w.evolution_record(
        task=f"{unique} fix edge cache bug",
        approach=f"{unique} traced cache key fallback path",
        tools_used=["grep"],
        outcome="success",
        lessons=[f"{unique} lesson B from second recording"],
    ))
    assert r2["status"] == "ok"
    assert r2["action"] == "merged"
    assert "merged_into" in r2


def test_export_and_import(w):
    """v2: export records to a file, then import them back."""
    # Record something with a unique marker so it won't dedup
    unique = "__export_import_test_marker__"
    _run(w.evolution_record(
        task=f"{unique} export import roundtrip",
        approach=f"{unique} record, export, clear, import",
        tools_used=["pytest"],
        outcome="success",
        lessons=[f"{unique} export then import should restore records"],
    ))
    # Export
    export_r = _run(w.evolution_export())
    assert export_r["status"] == "ok"
    assert export_r["exported"] >= 1
    export_path = export_r["path"]
    import os
    assert os.path.exists(export_path)

    # Clear
    _run(w.evolution_clear(confirm=True))

    # Import
    import_r = _run(w.evolution_import(input_path=export_path, merge=False))
    assert import_r["status"] == "ok"
    assert import_r["imported"] >= 1


def test_rollback_lists_snapshots(w):
    """v2: rollback with no snapshot_path lists available snapshots."""
    r = _run(w.evolution_rollback())
    assert r["status"] == "ok"
    assert "snapshots" in r


def test_prune_no_confirm(w):
    """v2: prune without confirm reports what *would* be pruned."""
    r = _run(w.evolution_prune(confirm=False))
    assert r["status"] == "ok"


def test_bm25_recall_ranking(w):
    """v2: BM25 recall returns scored results."""
    # Record a few lessons
    _run(w.evolution_record(
        task="optimize aiohttp server performance",
        approach="used connection pooling and keep-alive",
        tools_used=["aiohttp", "profiler"],
        outcome="success",
        lessons=["connection pooling reduces latency"],
        keywords=["aiohttp", "performance", "pooling"],
    ))
    _run(w.evolution_record(
        task="fix database migration error",
        approach="added missing alembic revision",
        tools_used=["alembic", "sqlalchemy"],
        outcome="success",
        lessons=["always check alembic heads before migrating"],
        keywords=["database", "alembic", "migration"],
    ))
    r = _run(w.evolution_recall("aiohttp performance optimization"))
    assert r["status"] == "ok"
    results = r.get("results", [])
    # Most relevant result should be about aiohttp
    if results:
        assert "aiohttp" in results[0].get("task", "").lower() or \
               "performance" in results[0].get("task", "").lower()

