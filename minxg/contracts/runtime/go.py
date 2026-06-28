"""Adapter: Go for system-adjacent utilities.

Go is a first-class MINXG runtime. The Python adapter ships real
``.go`` source files under ``minxg/contracts/runtime/assets/go`` and
runs them with ``go run``.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, which

ADAPTER_NAME = "go"
ADAPTER_VERSION = "0.14.0"
ADAPTER_STATUS = "disabled"

_GO = which("go")
_BRIDGE_GO = asset_path("go", "bridge.go")
_DEMO_GO = asset_path("go", "demo.go")
_GO_MOD = asset_path("go", "go.mod")

if _GO:
    ADAPTER_STATUS = "available"


def _run_go_file(go_file: Any, input_text: str = "") -> Dict[str, Any]:
    res = run([str(_GO), "run", str(go_file)],
              input_text=input_text,
              cwd=_GO_MOD.parent,
              timeout=20.0)
    return {
        "status": "ok" if res["ok"] else "runtime_error",
        "language": "go",
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def _read_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception as exc:
        return {"status": "runtime_error", "stderr": f"bad bridge output: {exc}"}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Go code through the shipped ``bridge.go`` with a JSON payload."""
    if not _GO:
        return {
            "status": "disabled",
            "language": "go",
            "hint": "Install Go and ensure 'go' is on PATH.",
        }
    code = payload_code(payload)
    raw_code = payload.get("code", "")
    if not raw_code.strip():
        # No custom code — run the demo asset.
        return _run_go_file(_DEMO_GO)
    request = json.dumps({"code": code})
    res = run([str(_GO), "run", str(_BRIDGE_GO)],
              input_text=request,
              cwd=_GO_MOD.parent,
              timeout=20.0)
    if not res["ok"]:
        return {
            "status": "runtime_error",
            "language": "go",
            "stdout": res["stdout"],
            "stderr": res["stderr"],
        }
    return _read_json(res["stdout"])


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)
