"""Adapter: Go for system-adjacent utilities and numeric compute.

Go is a first-class MINXG runtime. The Python adapter ships real
``.go`` source files under ``minxg/contracts/runtime/assets/go`` and
runs them with ``go run``.

Bridge modes (v0.16.0):
  - eval:     safe expression evaluator (sin/cos/sqrt/log/exp/pow + arithmetic)
  - fib:      Fibonacci O(log n) via matrix exponentiation
  - prime:    Sieve of Eratosthenes prime counting
  - fft:      naive DFT (O(n^2))
  - linsolve: Gaussian elimination Ax=b
  - matmul:   matrix multiplication
"""
from __future__ import annotations

import json
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, which

ADAPTER_NAME = "go"
ADAPTER_VERSION = "0.17.0"
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
    """Run Go code through the shipped ``bridge.go`` with a JSON payload.

    Payload shapes:
      {"file": "path/to/source.go"}             — go run that file
      {"code": "package main..."}                — run full Go source
      {"mode": "eval", "code": "sin(1)+2^10"}   — bridge eval mode
      {"mode": "fib", "n": 50}                   — bridge Fibonacci mode
      ... (see bridge.go for all modes)
    """
    if not _GO:
        return {
            "status": "disabled",
            "language": "go",
            "hint": "Install Go and ensure 'go' is on PATH.",
        }

    code = payload_code(payload)
    raw_code = payload.get("code", "")
    mode = payload.get("mode", "")

    # File mode
    file_path = payload.get("file", "")
    if file_path:
        return _run_go_file(file_path, input_text=json.dumps(payload))

    # Full source mode
    if raw_code.strip() and not mode and "package main" in raw_code:
        from ._exec import sandbox_path
        src = sandbox_path("go_user", raw_code, ".go")
        return _run_go_file(src, input_text="")

    # Bridge mode
    bridge_payload = dict(payload)
    if "mode" not in bridge_payload:
        bridge_payload["mode"] = "eval"
    if bridge_payload["mode"] == "eval" and not bridge_payload.get("code"):
        bridge_payload["code"] = "1 + 1"
    request = json.dumps(bridge_payload)
    res = run([str(_GO), "run", str(_BRIDGE_GO)],
              input_text=request,
              cwd=_GO_MOD.parent,
              timeout=20.0)
    if res["ok"]:
        parsed = _read_json(res["stdout"])
        if parsed.get("status"):
            return parsed
        return {"status": "ok", "language": "go", "stdout": res["stdout"]}
    return {
        "status": "runtime_error",
        "language": "go",
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for handle — used by the live adapter registry."""
    return handle(payload)


__all__ = [
    "ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS",
    "handle", "invoke",
]
