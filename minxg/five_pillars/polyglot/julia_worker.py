"""JuliaWorker — symbolic / numeric compute via the Julia bridge.

Real-world responsibilities inside MINXG:

* SymbDiff ground-truth: cross-check the Rust core's truncated-Taylor
  ``Jet`` derivatives against Julia's arbitrary-precision arithmetic.
* Self-evolution engine: when a candidate capability proposes a numeric
  formula, execute it in Julia to validate numerically before accepting
  the proposal.
* Driver engine: small-``n`` eigendecomposition is overkill in Rust with
  the LTO build, but Julia's LAPACK-backed ``eigen`` is the reference
  implementation we compare against.

Public tools match the bridge's mode surface (``eval``, ``fib``, ``prime``,
``linsolve``, ``eigen``, ``ode_step``, ``poly``).
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool

# Late-bind so test-time mocks can swap the runtime away without
# touching this module — same lazy-ref pattern as ``utils.ensure_config``.
import sys as _sys
_ADAPTER = _sys.modules.get("minxg.contracts.runtime.julia")


def _adapters():
    """Return the live adapter pair (adapter, status)."""
    return _ADAPTER, getattr(_ADAPTER, "ADAPTER_STATUS", "disabled")


class JuliaWorker(BaseWorker):
    worker_id = "julia_math"
    version = "0.17.1"

    # ── Tool surface ────────────────────────────────────────────────
    @tool(description="Evaluate a Julia expression via the bridge.",
          category="compute")
    async def julia_eval(self, code: str) -> Dict[str, Any]:
        adapter, status = _adapters()
        if status != "available":
            return self._disabled("evaluate expression", code[:60])
        return await self._invoke_async({"mode": "eval", "code": code})

    @tool(description="Compute Fibonacci(n) using Julia BigInt (O(n)).",
          category="compute")
    async def julia_fib(self, n: int) -> Dict[str, Any]:
        if n < 0 or n > 92:
            return self._bad_input("n must be in 0..92", {"n": n})
        adapter, status = _adapters()
        if status != "available":
            return self._disabled("fib", f"fib({n})")
        return await self._invoke_async({"mode": "fib", "n": n})

    @tool(description="Count primes <= n using Julia's sieve (n <= 1e7).",
          category="compute")
    async def julia_prime_count(self, n: int) -> Dict[str, Any]:
        if n < 0 or n > 10_000_000:
            return self._bad_input("n must be in 0..1e7", {"n": n})
        adapter, status = _adapters()
        if status != "available":
            return self._disabled("prime count", f"prime_count({n})")
        return await self._invoke_async({"mode": "prime", "n": n})

    @tool(description="Gaussian-elimination solve of A·x=b (n×n).",
          category="compute")
    async def julia_linsolve(self,
                              n: int,
                              a: List[float],
                              b: List[float]) -> Dict[str, Any]:
        if len(a) != n * n or len(b) != n:
            return self._bad_input("a must be n² entries, b must be n",
                                    {"n": n, "len_a": len(a), "len_b": len(b)})
        adapter, status = _adapters()
        if status != "available":
            return self._disabled("linsolve", f"{n}x{n} system")
        return await self._invoke_async({"mode": "linsolve",
                                         "n": n, "a": a, "b": b})

    @tool(description="Symmetric eigenvalues + eigenvectors of an n×n matrix.",
          category="compute")
    async def julia_eigen(self, n: int, a: List[float]) -> Dict[str, Any]:
        if len(a) != n * n:
            return self._bad_input("a must have exactly n² entries",
                                    {"n": n, "len_a": len(a)})
        adapter, status = _adapters()
        if status != "available":
            return self._disabled("eigen", f"{n}x{n}")
        return await self._invoke_async({"mode": "eigen",
                                         "n": n, "a": a})

    @tool(description="RK4 single-step integrator for dy/dx=f(x,y), n steps.",
          category="compute")
    async def julia_ode_step(self,
                              f: str,
                              x0: float,
                              y0: float,
                              h: float,
                              n: int) -> Dict[str, Any]:
        if not f:
            return self._bad_input("f expression cannot be empty", {})
        if h <= 0 or n < 0 or n > 100_000:
            return self._bad_input("positive h, 0..1e5 steps required",
                                    {"h": h, "n": n})
        adapter, status = _adapters()
        if status != "available":
            return self._disabled("ode_step", f"n={n}")
        return await self._invoke_async({"mode": "ode_step",
                                         "f": f, "x0": x0, "y0": y0,
                                         "h": h, "n": n})

    # ── Helpers ─────────────────────────────────────────────────────
    @staticmethod
    async def _invoke_async(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Off-load blocking subprocess to a worker thread.

        Tools never raise; if the adapter module isn't yet imported
        (``_ADAPTER is None``), return a well-formed disabled envelope so
        callers always see ``language: julia``.
        """
        loop = asyncio.get_running_loop()
        if _ADAPTER is None:
            return {
                "status": "disabled",
                "language": "julia",
                "tool": "unknown",
                "hint": "Julia adapter module not importable; check site-packages.",
            }
        return await loop.run_in_executor(
            None, lambda: _ADAPTER.invoke(payload)
        )

    @staticmethod
    def _disabled(verb: str, example: str) -> Dict[str, Any]:
        return {
            "status": "disabled",
            "language": "julia",
            "tool": verb,
            "hint": (
                "Julia runtime not installed. To enable: install Julia "
                "(pkg install julia on Termux) and add the JSON package "
                "(Pkg.add(\"JSON\")). Then call: minxg runtime-install julia "
                f"--apply. Was attempting: {example}"
            ),
        }

    @staticmethod
    def _bad_input(why: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "error",
            "language": "julia",
            "tool": "input_validation",
            "stderr": why,
            "context": context,
        }