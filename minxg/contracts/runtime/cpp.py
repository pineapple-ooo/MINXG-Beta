"""Adapter: native C / C++ via a system compiler.

C and C++ are first-class MINXG runtimes. The Python adapter ships real
``.c`` / ``.cpp`` bridge sources under
``minxg/contracts/runtime/assets/{c,cpp}`` and runs them by compiling with
``gcc`` / ``g++`` or ``clang`` / ``clang++``.

Usage modes:
  - ``{"file": "path/to/source.cpp"}`` — compile and run that file.
  - ``{"code": "int main(){...}"}`` — compile the full source.
  - ``{"code": "2 + 3"}`` — use the arithmetic bridge evaluator.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, sandbox_path, which

ADAPTER_NAME = "cpp"
ADAPTER_VERSION = "0.14.0"
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
    std_flag = "-std=c++17" if compiler.endswith(("g++", "clang++")) else "-std=c11"
    compile_res = run(
        [compiler, str(src_path), "-o", str(exe), "-O2", std_flag],
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
        "compiler": compiler,
        "stdout": run_res["stdout"],
        "stderr": run_res["stderr"],
    }


def _is_full_source(code: str) -> bool:
    return "int main" in code or "#include" in code or "intmain" in code.replace(" ", "")


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run C/C++ code by compiling a real source file."""
    compiler = _CXX or _CC
    if not compiler:
        return {
            "status": "disabled",
            "language": "cpp",
            "hint": "Install gcc/g++ or clang/clang++ to run C/C++.",
        }

    user_file = payload.get("file")
    if user_file and Path(user_file).is_file():
        return _compile_and_run(Path(user_file), compiler)

    code = payload_code(payload)
    if not code.strip() or code == "1 + 1":
        # No custom code — run the demo asset.
        src = _CPP_DEMO if _CXX else _C_DEMO
        return _compile_and_run(src, compiler)

    if _is_full_source(code):
        src = sandbox_path("cpp", code, ".cpp" if _CXX else ".c")
        return _compile_and_run(src, compiler)

    # Arithmetic expression — use the JSON bridge.
    import json
    src = _CPP_BRIDGE if _CXX else _C_BRIDGE
    request = json.dumps({"code": code})
    return _compile_and_run(src, compiler, input_text=request)


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)
