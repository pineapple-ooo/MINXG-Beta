"""Adapter: Datalog / ASP logic programming.

Datalog is a first-class MINXG runtime. The Python adapter ships real
``.lp`` source files under ``minxg/contracts/runtime/assets/datalog`` and
runs them with ``clingo`` (preferred) or ``pyDatalog`` (fallback).

Bridge modes (v0.16.0):
  - graph:     transitive closure, reachability, cycle detection, degrees
  - schedule:  resource-constrained scheduling
  - typecheck: Hindley-Milner style type inference
  - sets:      set intersection, union, subset check

No Python-string Datalog rules — rules live in ``.lp`` files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, sandbox_path, which

ADAPTER_NAME = "datalog"
ADAPTER_VERSION = "0.16.0"
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


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Datalog rules through clingo with the bridge predicates.

    Payload shapes:
      {"code": "edge(a,b). edge(b,c). reachable(X,Y) :- edge(X,Y)."} — custom rules
      {"file": "path/to/rules.lp"}                                      — run file
      {"mode": "demo"}                                                   — run the built-in demo
    """
    if not _CLINGO and not _HAS_PYDATALOG:
        return {
            "status": "disabled",
            "language": "datalog",
            "hint": "Install clingo (apt install clingo / pkg install clingo) or pip install pyDatalog",
        }

    raw_code = payload.get("code", "")
    file_path = payload.get("file", "")
    mode = payload.get("mode", "")

    # Demo mode: run the built-in demo
    if mode == "demo" or (not raw_code and not file_path):
        demo_src = _DEMO_LP.read_text(encoding="utf-8")
        return _run_clingo(demo_src)

    # File mode
    if file_path:
        src = Path(file_path)
        if not src.exists():
            return {"status": "error", "language": "datalog",
                    "stderr": f"file not found: {file_path}"}
        user_code = src.read_text(encoding="utf-8")
        return _run_clingo(user_code)

    # Code mode
    if raw_code.strip():
        return _run_clingo(raw_code)

    return {"status": "error", "language": "datalog",
            "stderr": "no code or file provided"}


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)


__all__ = [
    "ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS",
    "handle", "invoke",
]
