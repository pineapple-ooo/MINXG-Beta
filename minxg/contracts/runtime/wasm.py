"""Adapter: WebAssembly sandboxed compute.

Wasm is a first-class MINXG runtime. The Python adapter ships real
``.wat`` source files under ``minxg/contracts/runtime/assets/wasm`` and
runs them with ``wasmtime``. A tiny arithmetic emulator is kept as a
fallback only when no native runtime is installed.

No Python-string WASM — modules live in ``.wat`` files.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, sandbox_path, which

ADAPTER_NAME = "wasm"
ADAPTER_VERSION = "0.14.0"
ADAPTER_STATUS = "disabled"

_WASMTIME = which("wasmtime")
_MATH_WAT = asset_path("wasm", "math.wat")
_DEMO_WAT = asset_path("wasm", "demo.wat")

if _WASMTIME:
    ADAPTER_STATUS = "available"


def _pure_python_eval(code: str) -> Dict[str, Any]:
    """Fallback for simple arithmetic i32.add/sub/mul demos."""
    code = code.strip()
    const_re = re.compile(r"\(i32\.const\s+(-?\d+)\)")
    consts = [int(m.group(1)) for m in const_re.finditer(code)]
    result = None
    if len(consts) >= 2 and "i32.add" in code:
        result = consts[0] + consts[1]
    elif len(consts) >= 2 and "i32.sub" in code:
        result = consts[0] - consts[1]
    elif len(consts) >= 2 and "i32.mul" in code:
        result = consts[0] * consts[1]
    if result is not None:
        return {
            "status": "emulated",
            "language": "wasm",
            "stdout": str(result),
            "hint": "Install wasmtime for full WASI execution.",
        }
    return {
        "status": "emulated",
        "language": "wasm",
        "stdout": "no-runtime: use wasmtime for real WASM modules",
        "hint": "Install wasmtime for full WASI execution.",
    }


def _run_wasmtime(wat_path: Path, func: str = "", args: list = None) -> Dict[str, Any]:
    cmd = [str(_WASMTIME), "run"]
    if func:
        cmd.extend(["--invoke", func])
        if args:
            cmd.extend([str(a) for a in args])
    cmd.append(str(wat_path))
    res = run(cmd, timeout=15.0)
    return {
        "status": "ok" if res["ok"] else "runtime_error",
        "language": "wasm",
        "runtime": "wasmtime",
        "stdout": res["stdout"],
        "stderr": res["stderr"],
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a ``.wat`` module with wasmtime, or emulate a tiny demo."""
    func = payload.get("func", "")
    args = payload.get("args", [])

    # If user supplied a file path, use it directly.
    raw_code = payload.get("code", "")
    user_path = Path(raw_code)
    if user_path.is_file() and user_path.suffix in (".wat", ".wasm"):
        if _WASMTIME:
            return _run_wasmtime(user_path, func, args)
        return _pure_python_eval(raw_code)

    # No custom code? Run the demo asset.
    if not raw_code.strip():
        if _WASMTIME:
            return _run_wasmtime(_DEMO_WAT, "sum_to", [100])
        return {
            "status": "disabled",
            "language": "wasm",
            "hint": "Install wasmtime to run the shipped .wat assets.",
        }

    if _WASMTIME:
        # Write inline WAT to a temp file and execute it.
        path = sandbox_path("wasm", raw_code, ".wat")
        return _run_wasmtime(path, func, args)

    return _pure_python_eval(raw_code)


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)
