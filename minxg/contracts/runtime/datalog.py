"""Adapter: Datalog / ASP logic programming.

Datalog is a first-class MINXG runtime. The Python adapter ships real
``.lp`` source files under ``minxg/contracts/runtime/assets/datalog`` and
runs them with ``clingo`` (preferred) or ``pyDatalog`` (fallback).

No Python-string Datalog rules — rules live in ``.lp`` files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, sandbox_path, which

ADAPTER_NAME = "datalog"
ADAPTER_VERSION = "0.14.0"
ADAPTER_STATUS = "disabled"

_CLINGO = which("clingo")
_BRIDGE_LP = asset_path("datalog", "bridge.lp")
_DEMO_LP = asset_path("datalog", "demo.lp")
_HAS_PYDATALOG = False
try:
    import pyDatalog  # type: ignore[import-not-found] # noqa: F401
    _HAS_PYDATALOG = True
except Exception:
    pass

if _CLINGO or _HAS_PYDATALOG:
    ADAPTER_STATUS = "available"


def _run_clingo(user_code: str) -> Dict[str, Any]:
    """Combine bridge.lp with user code and run clingo."""
    bridge_src = _BRIDGE_LP.read_text(encoding="utf-8")
    combined = bridge_src + "\n\n% --- user code ---\n" + user_code
    src = sandbox_path("datalog", combined, ".lp")
    res = run([str(_CLINGO), "0", str(src)], timeout=20.0)
    return {
        "status": "ok" if res["ok"] else "runtime_error",
        "language": "datalog",
        "runtime": "clingo",
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def _run_pydatalog(user_code: str) -> Dict[str, Any]:
    import pyDatalog  # type: ignore[import-not-found]
    try:
        pyDatalog.clear()
        pyDatalog.load(user_code)
        query = user_code.split(":-")[0].strip()
        answers = pyDatalog.ask(query)
        return {
            "status": "ok",
            "language": "datalog",
            "runtime": "pyDatalog",
            "stdout": str(answers),
            "stderr": "",
        }
    except Exception as exc:
        return {
            "status": "runtime_error",
            "language": "datalog",
            "runtime": "pyDatalog",
            "stdout": "",
            "stderr": str(exc),
        }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Datalog/ASP code with clingo or pyDatalog."""
    code = payload_code(payload)
    if code in ("", "1 + 1"):
        # No custom code? Run the demo asset.
        code = _DEMO_LP.read_text(encoding="utf-8")
    if _CLINGO:
        return _run_clingo(code)
    if _HAS_PYDATALOG:
        return _run_pydatalog(code)
    return {
        "status": "disabled",
        "language": "datalog",
        "hint": "Install clingo (preferred) or pyDatalog to run Datalog.",
    }


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)
