"""tests/test_audit_worker.py -- AuditWorker tests."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.audit_worker import AuditWorker
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
    return AuditWorker()


def test_subclass(w):
    assert issubclass(AuditWorker, BaseWorker)


def test_worker_id(w):
    assert w.worker_id == "audit_tools"


def test_tier(w):
    assert w.tier == "code"


def test_audit_categories(w):
    r = _run(w.audit_categories())
    assert r["status"] == "ok"
    assert "categories" in r
    assert len(r["categories"]) >= 10


def test_audit_scan(w):
    """Scan the project and verify we get findings."""
    r = _run(w.audit_scan(max_findings=50))
    assert r["status"] == "ok"
    assert r["total_findings"] > 0
    assert "by_severity" in r
    assert "by_category" in r
    assert "findings" in r
    # Each finding has required fields
    if r["findings"]:
        f = r["findings"][0]
        assert "file" in f
        assert "line" in f
        assert "severity" in f
        assert "category" in f
        assert "message" in f


def test_audit_file_missing(w):
    r = _run(w.audit_file("/nonexistent/path.py"))
    assert r["status"] == "error"


def test_audit_file_real(w):
    """Audit a real file in the project."""
    target = str(Path(__file__).resolve().parent.parent / "minxg" / "base.py")
    r = _run(w.audit_file(target))
    assert r["status"] == "ok"
    assert "findings" in r
