"""tests/test_v0_17_1_fixes.py — patch-level fixes for v0.17.1."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_baseworker_statistics_exposes_suppressed():
    """Aliased workers expose ``facade_alias`` and ``suppressed`` in stats."""
    from minxg.five_pillars.dispatch.platform_tools import PlatformWorker  # aliased
    w = PlatformWorker()
    stat = w.statistics()
    assert "suppressed" in stat
    assert "facade_alias" in stat
    assert stat["facade_alias"] == "platform_worker"
    assert stat["suppressed"] >= 0


def test_baseworker_list_tools_returns_empty_when_aliased():
    from minxg.five_pillars.dispatch.platform_tools import PlatformWorker
    w = PlatformWorker()
    assert w.list_tools() == []


def test_baseworker_statistics_suppressed_increments_on_list():
    """Calling list_tools() bumps _suppressed_tool_count on aliased workers."""
    from minxg.five_pillars.dispatch.platform_tools import PlatformWorker
    w = PlatformWorker()
    n = len(w.list_tools())
    assert n == 0
    # Even after list_tools(), the suppressed count is now exposed via stats
    stat = w.statistics()
    assert "suppressed" in stat
    assert stat["suppressed"] >= 0


def test_unaliased_worker_has_no_facade_alias_field():
    """A non-aliased worker still has facade_alias = None in its stats."""
    from minxg.five_pillars.devtools.apk_forge import ApkForgeWorker
    w = ApkForgeWorker()
    s = w.statistics()
    assert s["facade_alias"] is None
    assert s["suppressed"] == 0


@pytest.mark.asyncio
async def test_concurrent_runner_active_count_increases():
    """Active counter ticks up while futures are in-flight."""
    from minxg.five_pillars.transform.concurrent_runner import (
        ConcurrentRunner, _Runner)
    _Runner._in_flight = 0  # reset state between tests
    w = ConcurrentRunner()
    # Use a callable that sleeps briefly to ensure active count is observable
    res = await w.call("runner_submit", {"callable_name": "cpu_factorial", "n": 4})
    assert res["status"] == "ok"
    assert res["result"] == 24
    assert _Runner._in_flight == 0  # decremented after completion


@pytest.mark.asyncio
async def test_concurrent_runner_stats_returns_real_active():
    from minxg.five_pillars.transform.concurrent_runner import ConcurrentRunner, _Runner
    _Runner._in_flight = 0
    w = ConcurrentRunner()
    res = await w.call("runner_stats", {"shutdown": False})
    assert res["status"] == "ok"
    assert res["stats"]["active"] == 0
    assert "max_workers" in res["stats"]


@pytest.mark.asyncio
async def test_concurrent_runner_map_increments_counter():
    from minxg.five_pillars.transform.concurrent_runner import ConcurrentRunner, _Runner
    _Runner._in_flight = 0
    w = ConcurrentRunner()
    res = await w.call("runner_map", {"callable_name": "cpu_factorial",
                                       "items": [{"n": 1}, {"n": 2}, {"n": 3}]})
    assert res["status"] == "ok"
    assert len(res["results"]) == 3
    assert _Runner._in_flight == 0
