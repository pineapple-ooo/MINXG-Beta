"""Adapter: R statistical / visualisation compute.

R is a first-class MINXG runtime. The Python side does not embed R source as
a string; it ships a real ``bridge.R`` under
``minxg/contracts/runtime/assets/r`` and invokes that file with a JSON payload
on stdin. R code lives in ``.R`` files, where it belongs.

Required: ``Rscript`` on PATH and the ``jsonlite`` package installed.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, which

ADAPTER_NAME = "r"
ADAPTER_VERSION = "0.14.0"
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
    """Run R code through ``bridge.R`` with a JSON payload."""
    if not _RSCRIPT:
        return {
            "status": "disabled",
            "language": "r",
            "hint": "Install R and ensure 'Rscript' is on PATH.",
        }
    if ADAPTER_STATUS != "available":
        return {
            "status": "disabled",
            "language": "r",
            "hint": "R needs the jsonlite package: install.packages(\"jsonlite\").",
        }
    code = payload_code(payload)
    request = json.dumps({"code": code})
    res = run([str(_RSCRIPT), str(_BRIDGE)], input_text=request, timeout=20.0)
    if not res["ok"]:
        return {
            "status": "runtime_error",
            "language": "r",
            "stdout": res["stdout"],
            "stderr": res["stderr"],
        }
    return _read_json(res["stdout"])


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)
