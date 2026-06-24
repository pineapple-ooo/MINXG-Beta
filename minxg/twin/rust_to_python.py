"""Rust → Python twin emitter, light scope.

Treats Rust function declarations of similar shape and emits Python
source. Used for in-process equivalence testing when you maintain a
hand-written Rust file alongside the Python twin.
"""
from __future__ import annotations
import re
from typing import List

from .mapper import TwinConfig, TwinResult, UnsupportedTwinOp


_RUST_TYPE_TO_PY = {
    "i64": "int",
    "i32": "int",
    "f64": "float",
    "f32": "float",
    "bool": "bool",
    "String": "str",
}


def rust_to_python(source: str, config: TwinConfig = None) -> TwinResult:
    config = config or TwinConfig()
    fn_match = re.search(
        r"pub fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([\w<>]+))?\s*\{(.*)\}",
        source,
        re.DOTALL,
    )
    if not fn_match:
        raise UnsupportedTwinOp("rust.parse", "expected a single pub fn with body")
    fn_name = fn_match.group(1)
    args_raw = fn_match.group(2).strip()
    body_raw = fn_match.group(4)
    args = _parse_rust_args(args_raw)
    body_lines = _parse_rust_body(body_raw)
    param_str = ", ".join(f"{name}: {_RUST_TYPE_TO_PY.get(typ, 'int')}" for name, typ in args)
    body = "\n".join(["    " + line for line in body_lines])
    src = f"def {fn_name}({param_str}):\n{body or '    return 0'}\n"
    return TwinResult(source=src, dependencies=[], warnings=[])


def _parse_rust_args(raw: str) -> List:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    out = []
    for part in parts:
        if ":" in part:
            name, typ = part.split(":", 1)
            out.append((name.strip(), typ.strip()))
        else:
            out.append((part, "i64"))
    return out


def _parse_rust_body(body: str) -> List[str]:
    lines: List[str] = []
    opens = 0
    for raw in body.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        opens += stripped.count("{") - stripped.count("}")
        if not stripped:
            continue
        if stripped.startswith("let "):
            stripped = re.sub(r"^let\s+(mut\s+)?", "", stripped)
            stripped = stripped.rstrip(";").replace(" = ", " = ", 1)
            lines.append(stripped)
        elif stripped.startswith("return "):
            expr = stripped[len("return "):].rstrip(";").strip()
            translated = expr.replace("true", "True").replace("false", "False")
            lines.append(f"return {translated}")
        elif stripped.startswith("if "):
            cond = stripped[len("if "):].rstrip("{").strip()
            cond = cond.replace("&&", "and").replace("||", "or")
            cond = cond.replace("true", "True").replace("false", "False")
            lines.append(f"{cond}:")
        elif stripped.startswith("}"):
            if opens <= 0:
                continue
            lines.append("# closing brace")
        elif stripped.startswith("for "):
            lines.append("# " + stripped)
        else:
            lines.append("# " + stripped)
    if not lines:
        lines.append("return 0")
    return lines
