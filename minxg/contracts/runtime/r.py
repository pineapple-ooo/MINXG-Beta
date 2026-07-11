"""Adapter: R statistical / visualisation compute.

R is a first-class MINXG runtime. The Python side does not embed R source as
a string; it ships a real ``bridge.R`` under
``minxg/contracts/runtime/assets/r`` and invokes that file with a JSON payload
on stdin. R code lives in ``.R`` files, where it belongs.

Bridge modes (v0.16.0):
  - eval:     safe R expression evaluator
  - fib:      Fibonacci (iterative, no recursion)
  - prime:    Sieve of Eratosthenes prime counting
  - linsolve: solve(A, b) for linear systems
  - summary:  full statistical summary (mean/sd/skew/kurt/quartiles)
  - hist:     histogram binning
  - regress:  simple linear regression with R-squared
  - cov:      covariance matrix

Required: ``Rscript`` on PATH and the ``jsonlite`` package installed.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, which

ADAPTER_NAME = "r"
ADAPTER_VERSION = "0.17.1"
ADAPTER_STATUS = "disabled"

_RSCRIPT = which("Rscript")
_BRIDGE = asset_path("r", "bridge.R")


def _probe() -> bool:
    """Check both the interpreter and the jsonlite package."""
    if not _RSCRIPT:
        return False
    code = (
        'if (!requireNamespace("jsonlite", quietly=TRUE)) '
        'quit(status=1) else cat("ok\\n")'
    )
    res = run([str(_RSCRIPT), "-e", code], timeout=10.0)
    return res["ok"] and "ok" in res["stdout"].splitlines()


if _probe():
    ADAPTER_STATUS = "available"


def _read_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception as exc:
        return {"status": "runtime_error", "stderr": f"bad bridge output: {exc}"}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run R code through the shipped ``bridge.R`` with a JSON payload.

    Payload shapes:
      {"mode": "eval", "code": "rnorm(100)"}                 — R eval
      {"mode": "fib", "n": 50}                                — Fibonacci
      {"mode": "prime", "n": 500000}                           — Prime sieve
      {"mode": "linsolve", "n": 3, "a": [...], "b": [...]}    — Linear solve
      {"mode": "summary", "data": [1.2, 3.4, ...]}            — Stats summary
      {"mode": "hist", "data": [...], "bins": 10}             — Histogram
      {"mode": "regress", "x": [...], "y": [...]}              — Regression
      {"mode": "cov", "data": [[1,2],[3,4],...]}               — Covariance
    """
    if not _RSCRIPT:
        return {
            "status": "disabled",
            "language": "r",
            "hint": "Install R and ensure 'Rscript' is on PATH, plus: install.packages('jsonlite')",
        }

    bridge_payload = dict(payload)
    if "mode" not in bridge_payload:
        bridge_payload["mode"] = "eval"
    if bridge_payload["mode"] == "eval" and not bridge_payload.get("code"):
        bridge_payload["code"] = "1 + 1"
    input_text = json.dumps(bridge_payload)

    res = run([str(_RSCRIPT), str(_BRIDGE)], input_text=input_text, timeout=30.0)
    if res["ok"]:
        parsed = _read_json(res["stdout"])
        if isinstance(parsed, dict) and parsed.get("status"):
            return parsed
        return {"status": "ok", "language": "r", "stdout": res["stdout"]}
    return {
        "status": "runtime_error",
        "language": "r",
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)


__all__ = [
    "ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS",
    "handle", "invoke",
]
