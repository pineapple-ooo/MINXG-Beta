"""Adapter: Julia high-performance scientific / numerical compute.

Julia is a first-class MINXG runtime. The Python side does not embed Julia
source as a string; it ships a real ``bridge.jl`` under
``minxg/contracts/runtime/assets/julia`` and invokes that file with a JSON
payload on stdin. Julia code lives in ``.jl`` files, where it belongs.

Bridge modes (v0.16.0):
  - eval:     safe expression evaluator
  - fib:      Fibonacci (BigInt iterative)
  - prime:    Sieve of Eratosthenes
  - linsolve: Gaussian elimination Ax=b
  - eigen:    eigenvalues + eigenvectors (symmetric)
  - ode_step: RK4 integration step
  - poly:     polynomial root-finding

Required: Julia binary on PATH and the ``JSON`` package installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, which

ADAPTER_NAME = "julia"
ADAPTER_VERSION = "0.17.0"
ADAPTER_STATUS = "disabled"

_JULIA = which("julia")
_BRIDGE = asset_path("julia", "bridge.jl")


def _probe() -> bool:
    """Check both the interpreter and the JSON package in one short call."""
    if not _JULIA:
        return False
    code = 'try using JSON; println("ok") catch e; println("missing-json") end'
    res = run([str(_JULIA), "-e", code], timeout=10.0)
    return res["ok"] and "ok" in res["stdout"].splitlines()


if _probe():
    ADAPTER_STATUS = "available"


def _read_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception as exc:
        return {"status": "runtime_error", "stderr": f"bad bridge output: {exc}"}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Julia code through the shipped ``bridge.jl`` with a JSON payload.

    Payload shapes:
      {"mode": "eval", "code": "sqrt(2) + exp(1)"}           — Julia eval
      {"mode": "fib", "n": 50}                                — Fibonacci BigInt
      {"mode": "prime", "n": 500000}                           — Prime sieve
      {"mode": "linsolve", "n": 3, "a": [...], "b": [...]}    — Linear solve
      {"mode": "eigen", "n": 3, "a": [...]}                    — Symmetric eigen
      {"mode": "ode_step", "f": "y", "x0": 0, "y0": 1, ...}   — RK4 step
      {"mode": "poly", "coeffs": [1, -3, 2]}                  — Polynomial roots
    """
    if not _JULIA:
        return {
            "status": "disabled",
            "language": "julia",
            "hint": "Install Julia and ensure 'julia' is on PATH, plus: Pkg.add(\"JSON\")",
        }

    bridge_payload = dict(payload)
    if "mode" not in bridge_payload:
        bridge_payload["mode"] = "eval"
    if bridge_payload["mode"] == "eval" and not bridge_payload.get("code"):
        bridge_payload["code"] = "1 + 1"
    input_text = json.dumps(bridge_payload)

    res = run([str(_JULIA), str(_BRIDGE)], input_text=input_text, timeout=30.0)
    if res["ok"]:
        parsed = _read_json(res["stdout"])
        if isinstance(parsed, dict) and parsed.get("status"):
            return parsed
        return {"status": "ok", "language": "julia", "stdout": res["stdout"]}
    return {
        "status": "runtime_error",
        "language": "julia",
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)


__all__ = [
    "ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS",
    "handle", "invoke",
]
