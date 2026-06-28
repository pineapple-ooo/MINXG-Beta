"""Adapter: Julia high-performance scientific / numerical compute.

Julia is a first-class MINXG runtime. The Python side does not embed Julia
source as a string; it ships a real ``bridge.jl`` under
``minxg/contracts/runtime/assets/julia`` and invokes that file with a JSON
payload on stdin. Julia code lives in ``.jl`` files, where it belongs.

Required: Julia binary on PATH and the ``JSON`` package installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, which

ADAPTER_NAME = "julia"
ADAPTER_VERSION = "0.14.0"
ADAPTER_STATUS = "disabled"

_JULIA = which("julia")
_BRIDGE = asset_path("julia", "bridge.jl")


def _probe() -> bool:
    """Check both the interpreter and the JSON package in one short call."""
    if not _JULIA:
        return False
    code = "try using JSON; println(\"ok\") catch e; println(\"missing-json\") end"
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
    """Run Julia code through ``bridge.jl`` with a JSON payload."""
    if not _JULIA:
        return {
            "status": "disabled",
            "language": "julia",
            "hint": "Install Julia and ensure 'julia' is on PATH.",
        }
    if ADAPTER_STATUS != "available":
        return {
            "status": "disabled",
            "language": "julia",
            "hint": "Julia needs the JSON package: using Pkg; Pkg.add(\"JSON\").",
        }
    code = payload_code(payload)
    request = json.dumps({"code": code, "mode": payload.get("mode", "eval")})
    res = run([str(_JULIA), str(_BRIDGE)], input_text=request, timeout=20.0)
    if not res["ok"]:
        return {
            "status": "runtime_error",
            "language": "julia",
            "stdout": res["stdout"],
            "stderr": res["stderr"],
        }
    return _read_json(res["stdout"])


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)
