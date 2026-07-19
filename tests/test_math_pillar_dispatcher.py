"""
tests/test_math_pillar_dispatcher.py — verify the seven-pillar math facade
exposes operators to the AI via the math_dispatch tool.

v0.18.3: the seven mathematical pillars previously sat behind facade_alias and
were unreachable from the AI layer.  ``MathPillarDispatcher`` adds
``math_dispatch`` + ``math_pillar_list`` as high-density facades.
"""
from __future__ import annotations

import asyncio
import os
import pytest


def test_import():
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher
    assert MathPillarDispatcher is not None


def test_dispatcher_indexes_major_pillars():
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher
    w = MathPillarDispatcher()
    pillars = set(w._ops_index.keys())
    # Six core pillars + the math_pillar geometry path
    assert {"ga", "cat", "infogeo", "topo", "chaos", "fiber"}.issubset(pillars)
    assert w._ops_count >= 50, f"too few ops indexed: {w._ops_count}"


def test_dispatcher_calls_chaos_logistic_lyapunov():
    """chaos.logistic_lyapunov(3.7) → chaotic, >0"""
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        r = await w.math_dispatch(pillar="chaos", op="logistic_lyapunov", r=3.7)
        return r

    res = asyncio.run(go())
    assert res["status"] == "ok"
    assert res["pillar"] == "chaos"
    assert res["op"] == "logistic_lyapunov"
    assert isinstance(res["result"], (int, float))
    assert res["result"] > 0.0, f"expected chaotic exponent >0, got {res['result']}"


def test_dispatcher_calls_chaos_logistic_lyapunov_periodic():
    """chaos.logistic_lyapunov(3.2) → periodic, <0"""
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        r = await w.math_dispatch(pillar="chaos", op="logistic_lyapunov", r=3.2)
        return r

    res = asyncio.run(go())
    assert res["status"] == "ok"
    assert res["result"] < 0.0, f"expected periodic exponent <0, got {res['result']}"


def test_dispatcher_lists_pillar_operations():
    """math_pillar_list returns the indexed operator names."""
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        return await w.math_pillar_list(pillar="chaos")

    res = asyncio.run(go())
    assert res["status"] == "ok"
    assert res["count"] > 0
    assert "logistic_lyapunov" in res["operations"]


def test_dispatcher_lists_all_pillars():
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        return await w.math_pillar_list()

    res = asyncio.run(go())
    assert res["status"] == "ok"
    assert "pillars" in res
    # Each pillar should have at least 1 op.
    for pillar, count in res["pillars"].items():
        assert count >= 1, f"pillar {pillar!r} has 0 operators"


def test_dispatcher_handles_unknown_pillar():
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        return await w.math_dispatch(pillar="imaginary_pillar", op="x")

    res = asyncio.run(go())
    assert res["status"] == "error"
    assert "unknown pillar" in res["error"]


def test_dispatcher_handles_unknown_op():
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        return await w.math_dispatch(pillar="chaos", op="doesnotexist_xyz")

    res = asyncio.run(go())
    assert res["status"] == "error"
    assert "unknown op" in res["error"]
    assert "did_you_mean" in res["hint"] if "hint" in res else True  # did_you_mean key optional


def test_dispatcher_statistics():
    """Statistics include the indexed pillar ops."""
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    w = MathPillarDispatcher()
    stats = w.statistics()
    assert "pillars_indexed" in stats
    assert "total_pillar_ops" in stats
    assert stats["total_pillar_ops"] >= 50


def test_dispatcher_resilient_to_bad_args():
    """When op receives a TypeError (e.g. missing required arg),
    dispatcher returns a structured error rather than crashing."""
    from minxg.five_pillars.devtools.math_pillar_dispatcher import MathPillarDispatcher

    async def go():
        w = MathPillarDispatcher()
        # log_lyapunov expects a 'r' kwarg; pass nothing.
        return await w.math_dispatch(pillar="chaos", op="logistic_lyapunov")

    res = asyncio.run(go())
    # Either it gets a default n or it gracefully errors.
    assert res["status"] in {"ok", "error"}
