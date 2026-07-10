"""Adapter: native C / C++ via a system compiler.

C and C++ are first-class MINXG runtimes. The Python adapter ships real
``.c`` / ``.cpp`` bridge sources under
``minxg/contracts/runtime/assets/{c,cpp}`` and runs them by compiling with
``gcc`` / ``g++`` or ``clang`` / ``clang++``.

Bridge modes (v0.16.0):
  - eval:     safe expression evaluator (sin/cos/sqrt/log/exp/pow + arithmetic)
  - fib:      Fibonacci O(log n) via matrix exponentiation
  - prime:    Sieve of Eratosthenes prime counting
  - fft:      naive DFT (O(n^2), real-only)
  - linsolve: Gaussian elimination Ax=b
  - det:      determinant via LU (C++ only)
  - eigen3:   3x3 symmetric eigenvalues (C++ only)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, sandbox_path, which

ADAPTER_NAME = "cpp"
ADAPTER_VERSION = "0.17.0"
ADAPTER_STATUS = "disabled"

_CC = which("gcc") or which("clang")
_CXX = which("g++") or which("clang++")
_C_BRIDGE = asset_path("c", "bridge.c")
_CPP_BRIDGE = asset_path("cpp", "bridge.cpp")
_C_DEMO = asset_path("c", "demo.c")
_CPP_DEMO = asset_path("cpp", "demo.cpp")

if _CC or _CXX:
    ADAPTER_STATUS = "available"


def _compile_and_run(src_path: Path, compiler: str,
                     input_text: str = "") -> Dict[str, Any]:
    exe = sandbox_path("cpp_bin", "", "")
    exe = exe.with_suffix("" if os.name != "nt" else ".exe")
    is_cpp = compiler.endswith(("g++", "clang++"))
    std_flag = "-std=c++17" if is_cpp else "-std=c11"
    lib_flag = "-lm" if not is_cpp else ""
    compile_res = run(
        [compiler, str(src_path), "-o", str(exe), "-O2", std_flag, lib_flag],
        timeout=20.0,
    )
    if not compile_res["ok"]:
        return {
            "status": "compile_error",
            "language": "cpp",
            "stdout": compile_res["stdout"],
            "stderr": compile_res["stderr"],
        }
    run_res = run([str(exe)], input_text=input_text, timeout=10.0)
    return {
        "status": "ok" if run_res["ok"] else "runtime_error",
        "language": "cpp",
        "stdout": run_res["stdout"],
        "stderr": run_res["stderr"],
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch C/C++ code through the industrial-grade bridge.

    Payload shapes:
      {"file": "path/to/source.c"}       — compile and run that file
      {"code": "int main(){...}"}         — compile the full source
      {"mode": "eval", "code": "sin(1)+2^10"} — bridge eval mode
      {"mode": "fib", "n": 50}            — bridge Fibonacci mode
      ... (see bridge.c/bridge.cpp for all modes)
    """
    if not _CC and not _CXX:
        return {
            "status": "disabled",
            "language": "cpp",
            "hint": "Install gcc/clang or g++/clang++ and ensure it is on PATH.",
        }

    raw_code = payload.get("code", "")
    file_path = payload.get("file", "")
    mode = payload.get("mode", "")

    # File mode: compile the given file
    if file_path:
        src = Path(file_path)
        if not src.exists():
            return {"status": "error", "language": "cpp",
                    "stderr": f"file not found: {file_path}"}
        is_cpp_file = src.suffix in (".cpp", ".cxx", ".cc", ".C")
        compiler = str(_CXX if is_cpp_file and _CXX else (_CC or _CXX))
        return _compile_and_run(src, compiler)

    # Full source mode: user provided a complete program
    if raw_code.strip() and not mode:
        # Heuristic: if it has main(), it's a full program
        if "main" in raw_code:
            is_cpp = "iostream" in raw_code or "using namespace" in raw_code
            suffix = ".cpp" if is_cpp else ".c"
            compiler = str(_CXX if is_cpp and _CXX else (_CC or _CXX))
            src = sandbox_path("cpp_user", raw_code, suffix)
            return _compile_and_run(src, compiler)

    # Bridge mode: dispatch to the pre-built bridge
    import json
    is_cpp_mode = mode in ("det", "eigen3") if mode else False
    if is_cpp_mode and _CXX:
        bridge = _CPP_BRIDGE
        compiler = str(_CXX)
    elif is_cpp_mode and not _CXX:
        return {"status": "error", "language": "cpp",
                "stderr": "C++ compiler required for this mode"}
    else:
        # Default to C bridge for eval/fib/prime/fft/linsolve
        bridge = _C_BRIDGE if _CC else _CPP_BRIDGE
        compiler = str(_CC if _CC else _CXX)

    # Prepare JSON payload for the bridge
    bridge_payload = dict(payload)
    if "mode" not in bridge_payload:
        bridge_payload["mode"] = "eval"
    if bridge_payload["mode"] == "eval" and not bridge_payload.get("code"):
        bridge_payload["code"] = "1 + 1"
    input_text = json.dumps(bridge_payload)

    src = sandbox_path("cpp_bridge_run", "", "")
    result = _compile_and_run(bridge, compiler, input_text=input_text)

    # Try to parse JSON from stdout
    if result["status"] == "ok" and result.get("stdout"):
        try:
            parsed = json.loads(result["stdout"])
            return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return result


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for handle — used by the live adapter registry."""
    return handle(payload)


__all__ = [
    "ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS",
    "handle", "invoke",
]
