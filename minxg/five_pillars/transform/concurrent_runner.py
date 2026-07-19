"""minxg/five_pillars/transform/concurrent_runner.py — async worker thread pool.

Provides a thread-enqueued runner so heavy tool calls (FFI, file I/O) don't
block the asyncio loop. Uses ``loop.run_in_executor`` + ``ThreadPoolExecutor``
managed at module scope; the pool is lazy and per-process.

Public API:

* ``ConcurrentRunner.submit(callable, *args, **kwargs)`` returns a future
* ``ConcurrentRunner.map(callback, items)`` returns list
* ``ConcurrentRunner.shutdown()`` for clean shutdown

Why a worker? So the AI can spawn jobs, cancel them, or pool-compute
on user demand — and so we can introspect ``runner.stats()`` through the
overall ``minxg`` tool surface.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import (
    Future, ThreadPoolExecutor, wait, FIRST_COMPLETED, CancelledError,
)
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

T = TypeVar("T")
from minxg.base import BaseWorker, tool


class _Runner:
    """Process-scoped thread pool, lazy."""

    _pool: Optional[ThreadPoolExecutor] = None
    _max_workers: int = 8
    _in_flight: int = 0  # tracked under submit/map calls

    @classmethod
    def pool(cls) -> ThreadPoolExecutor:
        if cls._pool is None:
            cls._pool = ThreadPoolExecutor(
                max_workers=cls._max_workers,
                thread_name_prefix="minxg-runner",
            )
        return cls._pool

    @classmethod
    def shutdown(cls) -> None:
        if cls._pool is not None:
            cls._pool.shutdown(wait=False, cancel_futures=True)
            cls._pool = None


class ConcurrentRunner(BaseWorker):
    """Async-first thread pool worker.

    Tools expose 3 verbs, not 10 micro-helpers. Each ``submit`` is a thin
    layer over ``run_in_executor``.
    """

    worker_id = "concurrent_runner"
    tier = "code"  # v0.18.0 three-tier classification
    version = "0.17.1"
    _category = "scheduler"

    @staticmethod
    def _stats() -> Dict[str, int]:
        pool = _Runner.pool()
        return {
            "max_workers": pool._max_workers
            if hasattr(pool, "_max_workers")
            else _Runner._max_workers,
            "active": _Runner._in_flight,
        }

    @tool(
        description=(
            "Submit a sync callable to a thread pool; returns its result "
            "after the loop yields. The callable runs off the asyncio loop, "
            "so it can block on subprocess / FFI / disk without stalling the "
            "gateway. ``payload`` is forwarded as kwargs."
        ),
        category="scheduler",
    )
    async def runner_submit(
        self, callable_name: str, **payload: Any,
    ) -> Dict:
        # we look up the callable in a small registry; direct callables are
        # not safe across processes. Resolve from a fixed picker.
        fn = _REGISTRY.get(callable_name)
        if fn is None:
            return {
                "status": "error",
                "error": f"unknown callable {callable_name!r}",
                "available": sorted(_REGISTRY.keys()),
            }
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(_Runner.pool(), lambda: fn(**payload))
        # await result with a soft cap of 5 minutes; AI tools should err early,
        # long-blocking work runs via cronjob
        try:
            res = await asyncio.wait_for(fut, timeout=300)
            return {"status": "ok", "result": res, "stats": self._stats()}
        except asyncio.TimeoutError:
            return {"status": "timeout", "callable": callable_name}

    @tool(
        description=(
            "Map a named callable across a JSON list of payloads, returning "
            "all results in submission order. Returns list of either "
            "{ok, result} or {error} dicts — never throws."
        ),
        category="scheduler",
    )
    async def runner_map(
        self, callable_name: str, items: List[Dict[str, Any]],
    ) -> Dict:
        fn = _REGISTRY.get(callable_name)
        if fn is None:
            return {
                "status": "error",
                "error": f"unknown callable {callable_name!r}",
                "available": sorted(_REGISTRY.keys()),
            }
        if len(items) > 1024:
            return {"status": "error", "error": "too many items (cap 1024)"}

        loop = asyncio.get_running_loop()
        futures = [
            loop.run_in_executor(_Runner.pool(), lambda p=p: _safe(fn, **p))
            for p in items
        ]
        out: List[Dict] = []
        for f in futures:
            try:
                r = await asyncio.wait_for(f, timeout=600)
            except asyncio.TimeoutError:
                r = {"status": "timeout"}
            out.append(r)
        return {"status": "ok", "results": out, "count": len(out),
                "stats": self._stats()}

    @tool(
        description=(
            "Return pool stats and shutdown. shutdown=True cancels pending "
            "futures; the pool is recreated lazily on the next submit."
        ),
        category="scheduler",
    )
    async def runner_stats(self, shutdown: bool = False) -> Dict:
        if shutdown:
            _Runner.shutdown()
        return {"status": "ok", "stats": self._stats()}


# ─── Registry: thread-safe pickable callables users can run in pool ──────────


def _safe(fn: Callable[..., Any], **kw: Any) -> Dict[str, Any]:
    if fn is None:
        return {"status": "error", "error": "callable None"}
    _Runner._in_flight += 1
    try:
        return {"status": "ok", "result": fn(**kw)}
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    finally:
        _Runner._in_flight -= 1


def _cpu_factorial(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    out = 1
    for k in range(2, n + 1):
        out *= k
    return out


def _cpu_hash_text(text: str) -> int:
    h = 0xcbf29ce484222325
    for ch in text.encode("utf-8"):
        h ^= ch
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def _font_config_dummy(**_) -> Dict[str, int]:
    """Returns diagnostics for parallelism. Pure-Python, no I/O."""
    return {
        "host_cpu_count": 1,  # Termux typically caps threads; we lie-low
        "free_gb": 1.0,
        "now": int(time.time()),
    }


_REGISTRY: Dict[str, Callable[..., Any]] = {
    "cpu_factorial": _cpu_factorial,
    "cpu_hash_text": _cpu_hash_text,
    "font_config_dummy": _font_config_dummy,
}
