"""RWorker — statistical analysis via the R ``jsonlite`` bridge.

Real-world responsibilities inside MINXG:

* Analytics tracker — full ``summary()`` on log arrays without pulling
  NumPy/SciPy, helpful on Termux where scipy tends to be large.
* Driver engine — fit a regression through observed-state time-series to
  detect energy drift; flag a singularity before it cascades.
* Lens ``glossary.py`` — produce distribution tables that translate
  cleanly across languages via the JSON payload protocol.

Public tools: ``r_summary``, ``r_hist``, ``r_regress``, ``r_cov``,
``r_eval``, ``r_fib``, ``r_linsolve``, ``r_prime_count``.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool

import sys as _sys
_ADAPTER = _sys.modules.get("minxg.contracts.runtime.r")


class RWorker(BaseWorker):
    worker_id = "r_stats"
    version = "0.16.0"

    @tool(description="Full statistical summary (mean/sd/quartiles/skew/kurt).",
          category="stats")
    async def r_summary(self, data: List[float]) -> Dict[str, Any]:
        self._require_len(data)
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("r_summary", f"n={len(data)}")
        return await self._invoke_async({"mode": "summary", "data": data})

    @tool(description="Histogram with N bins (default 10).",
          category="stats")
    async def r_hist(self, data: List[float], bins: int = 10) -> Dict[str, Any]:
        if bins <= 0 or bins > 1000:
            return self._bad_input("bins in 1..1000", {"bins": bins})
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("r_hist", f"bins={bins}")
        return await self._invoke_async(
            {"mode": "hist", "data": data, "bins": bins})

    @tool(description="Simple linear regression y = a·x + b with R².",
          category="stats")
    async def r_regress(self, x: List[float], y: List[float]) -> Dict[str, Any]:
        if len(x) != len(y) or len(x) < 2:
            return self._bad_input("x,y same length (>= 2) required",
                                    {"len_x": len(x), "len_y": len(y)})
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("r_regress", f"n={len(x)}")
        return await self._invoke_async({"mode": "regress", "x": x, "y": y})

    @tool(description="Covariance matrix of N data points in D dimensions.",
          category="stats")
    async def r_cov(self, data: List[List[float]]) -> Dict[str, Any]:
        if len(data) < 2:
            return self._bad_input("at least 2 data points required",
                                    {"n": len(data)})
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("r_cov", f"n={len(data)}")
        return await self._invoke_async({"mode": "cov", "data": data})

    @tool(description="Evaluate a stateless R expression in a sandboxed env.",
          category="compute")
    async def r_eval(self, code: str) -> Dict[str, Any]:
        if not code:
            return self._bad_input("code cannot be empty", {})
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("r_eval", code[:40])
        return await self._invoke_async({"mode": "eval", "code": code})

    @tool(description="Compute fib(n) (0..92) — useful for cross-runtime tests.",
          category="compute")
    async def r_fib(self, n: int) -> Dict[str, Any]:
        if n < 0 or n > 92:
            return self._bad_input("n in 0..92", {"n": n})
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("r_fib", f"n={n}")
        return await self._invoke_async({"mode": "fib", "n": n})

    # ── Helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _require_len(data):
        if data is None or len(data) == 0:
            raise ValueError("data list cannot be empty")

    @staticmethod
    def _status() -> str:
        return getattr(_ADAPTER, "ADAPTER_STATUS", "disabled")

    @staticmethod
    async def _invoke_async(payload: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        if _ADAPTER is None:
            return {
                "status": "disabled",
                "language": "r",
                "tool": "unknown",
                "hint": "R adapter module not importable; check site-packages.",
            }
        return await loop.run_in_executor(
            None, lambda: _ADAPTER.invoke(payload)
        )

    @staticmethod
    def _disabled(verb: str, example: str) -> Dict[str, Any]:
        return {
            "status": "disabled",
            "language": "r",
            "tool": verb,
            "hint": (
                "R runtime not installed. To enable: install R "
                "(apt install r-base / pkg install r) and add jsonlite "
                "(install.packages(\"jsonlite\")). Then: "
                f"minxg runtime-install r --apply. Was attempting: {example}"
            ),
        }

    @staticmethod
    def _bad_input(why: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "error",
            "language": "r",
            "tool": "input_validation",
            "stderr": why,
            "context": context,
        }