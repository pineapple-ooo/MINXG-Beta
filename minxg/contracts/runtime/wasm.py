"""Adapter: WebAssembly sandboxed compute.

Wasm is a first-class MINXG runtime. The Python adapter ships real
``.wat`` source files under ``minxg/contracts/runtime/assets/wasm`` and
runs them with ``wasmtime``. A tiny arithmetic emulator is kept as a
fallback only when no native runtime is installed.

Bridge modes (v0.14.1 — via wasmtime invoke):
  - add/sub/mul/div/mod   — i32 arithmetic
  - fadd/fsub/fmul/fdiv   — f64 IEEE-754 arithmetic
  - fib                   — Fibonacci via fast doubling O(log n)
  - factorial             — iterative factorial
  - gcd                   — Euclidean GCD
  - is_prime              — trial division primality
  - mat_det3              — 3x3 determinant (f64)
  - mandelbrot            — Mandelbrot iteration count

No Python-string WASM — modules live in ``.wat`` files.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from ._exec import asset_path, payload_code, run, sandbox_path, which

ADAPTER_NAME = "wasm"
ADAPTER_VERSION = "0.14.1"
ADAPTER_STATUS = "disabled"

_WASMTIME = which("wasmtime")
_MATH_WAT = asset_path("wasm", "math.wat")
_DEMO_WAT = asset_path("wasm", "demo.wat")

if _WASMTIME:
    ADAPTER_STATUS = "available"


def _pure_python_eval(code: str) -> Dict[str, Any]:
    """Fallback for simple arithmetic when no wasm runtime is available.

    Supports: i32.add, i32.sub, i32.mul, i32.div_s, i32.rem_s
    and the extended function-call syntax: fib(30), is_prime(97), etc.
    """
    code = code.strip()
    const_re = re.compile(r"\(i32\.const\s+(-?\d+)\)")
    consts = [int(m.group(1)) for m in const_re.finditer(code)]
    result = None

    # Extended function names
    func_call_re = re.compile(r"(\w+)\(([^)]*)\)")
    for m in func_call_re.finditer(code):
        fname = m.group(1)
        args_str = m.group(2).strip()
        args = []
        if args_str:
            for a in args_str.split(","):
                a = a.strip()
                try:
                    args.append(int(a))
                except ValueError:
                    try:
                        args.append(float(a))
                    except ValueError:
                        pass

        if fname == "fib" and len(args) >= 1:
            n = args[0]
            if n <= 0:
                result = 0
            elif n == 1:
                result = 1
            else:
                a, b = 0, 1
                for _ in range(2, n + 1):
                    a, b = b, a + b
                result = b
        elif fname == "factorial" and len(args) >= 1:
            n = args[0]
            r = 1
            for i in range(2, n + 1):
                r *= i
            result = r
        elif fname == "gcd" and len(args) >= 2:
            a, b = abs(args[0]), abs(args[1])
            while b:
                a, b = b, a % b
            result = a
        elif fname == "is_prime" and len(args) >= 1:
            n = args[0]
            if n < 2:
                result = 0
            elif n == 2:
                result = 1
            elif n % 2 == 0:
                result = 0
            else:
                result = 1
                i = 3
                while i * i <= n:
                    if n % i == 0:
                        result = 0
                        break
                    i += 2
        elif fname == "mandelbrot" and len(args) >= 2:
            cx, cy = float(args[0]), float(args[1])
            zx = zy = 0.0
            iter_count = 0
            while iter_count < 255 and zx*zx + zy*zy <= 4.0:
                tmp = zx*zx - zy*zy + cx
                zy = 2*zx*zy + cy
                zx = tmp
                iter_count += 1
            result = iter_count

    # Basic i32 arithmetic fallback
    if result is None and len(consts) >= 2:
        if "i32.add" in code:
            result = consts[0] + consts[1]
        elif "i32.sub" in code:
            result = consts[0] - consts[1]
        elif "i32.mul" in code:
            result = consts[0] * consts[1]
        elif "i32.div_s" in code:
            if consts[1] != 0:
                result = consts[0] // consts[1]
        elif "i32.rem_s" in code:
            if consts[1] != 0:
                result = consts[0] % consts[1]

    if result is not None:
        return {
            "status": "ok",
            "language": "wasm",
            "runtime": "pure-python-fallback",
            "result": result,
        }
    return {
        "status": "runtime_error",
        "language": "wasm",
        "runtime": "pure-python-fallback",
        "stderr": "unsupported expression; install wasmtime for full wasm support",
    }


def _compile_wat(wat_path: Path) -> Dict[str, Any]:
    """Compile .wat to .wasm using wasmtime."""
    wasm_path = wat_path.with_suffix(".wasm")
    res = run([str(_WASMTIME), "compile", str(wat_path), "-o", str(wasm_path)],
              timeout=15.0)
    if not res["ok"]:
        return {"status": "compile_error", "language": "wasm",
                "stderr": res["stderr"]}
    return {"status": "ok", "wasm_path": str(wasm_path)}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Wasm through the shipped ``math.wat`` / ``demo.wat`` with wasmtime.

    Payload shapes:
      {"func": "add", "args": [3, 4]}              — call a wasm function
      {"func": "fib", "args": [30]}                 — Fibonacci
      {"func": "mandelbrot", "args": [-0.5, 0.0]}   — Mandelbrot sample
      {"mode": "demo"}                              — run demo.wat
      {"wat": "..."}                                — compile & run raw WAT (fallback)
      {"code": "fib(30)"}                           — pure-Python fallback expression
    """
    mode = payload.get("mode", "")
    func_name = payload.get("func", "")
    args = payload.get("args", [])

    # Demo mode
    if mode == "demo" or (not func_name and not payload.get("code")):
        if _WASMTIME:
            res = run([str(_WASMTIME), "run", "--invoke", "fib", str(_DEMO_WAT), "30"],
                      timeout=10.0)
            if res["ok"]:
                return {"status": "ok", "language": "wasm",
                        "runtime": "wasmtime", "stdout": res["stdout"].strip()}
            return {"status": "runtime_error", "language": "wasm",
                    "stderr": res["stderr"]}
        return _pure_python_eval("fib(30)")

    # Function call mode with wasmtime
    if func_name and _WASMTIME:
        # Build wasmtime command with --invoke
        str_args = [str(a) for a in args]
        # Determine wat file: mandelbrot/fib/is_prime use demo.wat; math ops use math.wat
        wat_file = _MATH_WAT if func_name in (
            "add", "sub", "mul", "div", "mod",
            "fadd", "fsub", "fmul", "fdiv",
            "fib", "factorial", "gcd", "is_prime",
            "mat_det3", "mandelbrot",
        ) else _DEMO_WAT
        cmd = [str(_WASMTIME), "run", "--invoke", func_name, str(wat_file)] + str_args
        res = run(cmd, timeout=10.0)
        if res["ok"]:
            return {"status": "ok", "language": "wasm",
                    "runtime": "wasmtime", "result": res["stdout"].strip()}
        return {"status": "runtime_error", "language": "wasm",
                "stderr": res["stderr"]}

    # Pure-Python fallback
    if payload.get("code") or func_name:
        code = payload.get("code", f"{func_name}({','.join(str(a) for a in args)})")
        return _pure_python_eval(code)

    return {"status": "error", "language": "wasm",
            "stderr": "no func, code, or mode specified"}


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    return handle(payload)


__all__ = [
    "ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS",
    "handle", "invoke",
]
