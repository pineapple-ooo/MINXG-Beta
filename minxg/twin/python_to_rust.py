"""Python → Rust twin emitter.

Covers the operator subset:

  * function definitions with positional and keyword arguments
  * assignments to integer, float, boolean, string and list targets
  * for / while loops
  * if / elif / else
  * return
  * calls of the form `name(a, b, c=...)` where `name` is in the
    function's known operator table

Anything else raises UnsupportedTwinOp. The emitter returns the source
of a Rust *function* (no module-level boilerplate so the caller can
choose how to wrap it).
"""
from __future__ import annotations
import ast
import re
from typing import Dict, List, Tuple

from .mapper import TwinConfig, TwinResult, UnsupportedTwinOp


_RUST_OPS: Dict[str, str] = {
    "Add": "({a}) + ({b})",
    "Sub": "({a}) - ({b})",
    "Mul": "({a}) * ({b})",
    "Div": "({a}) / ({b})",
    "Mod": "({a}) % ({b})",
}


_TYPE_HINTS_PYTHON = {
    "int": "i64",
    "float": "f64",
    "bool": "bool",
    "str": "String",
}


def python_to_rust(source: str, config: TwinConfig = None) -> TwinResult:
    config = config or TwinConfig()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise UnsupportedTwinOp("python.parse", str(e))
    fn = _extract_function(tree)
    if fn is None:
        raise UnsupportedTwinOp("python.top_level", "expected single function definition")
    dependencies, warnings = _gather_dependencies(tree)
    args = _rust_args(fn, config)
    body, more_warnings = _emit_body(fn.body, config)
    warnings.extend(more_warnings)
    src_lines = [
        f"pub fn {config.function_name}({args}) -> i64 {{",
        *body,
        "}",
    ]
    return TwinResult(
        source="\n".join(src_lines),
        dependencies=dependencies,
        warnings=warnings,
    )


def _extract_function(tree: ast.AST):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node
    return None


def _gather_dependencies(tree: ast.AST) -> Tuple[List[str], List[str]]:
    deps: List[str] = []
    warnings: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                deps.append(node.module)
    return sorted(set(deps)), warnings


def _rust_args(fn: ast.FunctionDef, config: TwinConfig) -> str:
    parts = []
    for arg in fn.args.args:
        ann = _annotation_to_rust(arg.annotation, config) if arg.annotation else "i64"
        parts.append(f"{arg.arg}: {ann}")
    return ", ".join(parts) or ""


def _annotation_to_rust(node, config: TwinConfig):
    if isinstance(node, ast.Name):
        return _TYPE_HINTS_PYTHON.get(node.id, "i64")
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _TYPE_HINTS_PYTHON.get(node.value, "i64")
    return "i64"


def _emit_body(stmts: List[ast.stmt], config: TwinConfig) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    lines: List[str] = []
    for stmt in stmts:
        emitted, more = _emit_stmt(stmt, config, indent=1)
        warnings.extend(more)
        lines.extend(emitted)
    if not lines:
        lines.append("    0")
    return lines, warnings


def _emit_stmt(stmt: ast.stmt, config: TwinConfig, indent: int) -> Tuple[List[str], List[str]]:
    pad = "    " * indent
    warnings: List[str] = []

    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            raise UnsupportedTwinOp("python.assign_target", "only single-name targets supported")
        target = stmt.targets[0].id
        value = _emit_expr(stmt.value, config, warnings)
        rust_type = _infer_rust_type(stmt.value)
        return [f"{pad}let mut {target}: {rust_type} = {value};"], warnings

    if isinstance(stmt, ast.AugAssign):
        if not isinstance(stmt.target, ast.Name):
            raise UnsupportedTwinOp("python.augassign_target", "")
        op_mapping = {
            ast.Add: "+=", ast.Sub: "-=", ast.Mult: "*=", ast.Div: "/=", ast.Mod: "%=",
        }
        op = op_mapping.get(type(stmt.op))
        if op is None:
            raise UnsupportedTwinOp("python.augassign_op", type(stmt.op).__name__)
        rhs = _emit_expr(stmt.value, config, warnings)
        return [f"{pad}{stmt.target.id} {op} {rhs};"], warnings

    if isinstance(stmt, ast.If):
        lines = _emit_if(stmt, config, indent, warnings)
        return lines, warnings

    if isinstance(stmt, ast.For):
        if not isinstance(stmt.target, ast.Name):
            raise UnsupportedTwinOp("python.for_target", "")
        if not isinstance(stmt.iter, ast.Call):
            raise UnsupportedTwinOp("python.for_iter", "iter must be range(...)")
        if not isinstance(stmt.iter.func, ast.Name) or stmt.iter.func.id != "range":
            raise UnsupportedTwinOp("python.for_iter", "iter must be range(...)")
        args = stmt.iter.args
        if len(args) == 1:
            start, stop = "0", _emit_expr(args[0], config, warnings)
        elif len(args) == 2:
            start, stop = _emit_expr(args[0], config, warnings), _emit_expr(args[1], config, warnings)
        else:
            start = _emit_expr(args[0], config, warnings)
            stop = _emit_expr(args[1], config, warnings)
            warnings.append("for-range step ignored in tail call")
        lines = [f"{pad}for {stmt.target.id} in {start}..{stop} {{"]
        inner, more = _emit_body(stmt.body, config)
        warnings.extend(more)
        lines.extend(inner)
        lines.append(f"{pad}}}")
        return lines, warnings

    if isinstance(stmt, ast.While):
        cond = _emit_expr(stmt.test, config, warnings)
        lines = [f"{pad}while {cond} {{"]
        inner, more = _emit_body(stmt.body, config)
        warnings.extend(more)
        lines.extend(inner)
        lines.append(f"{pad}}}")
        return lines, warnings

    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return [f"{pad}return 0;"], warnings
        expr = _emit_expr(stmt.value, config, warnings)
        return [f"{pad}return {expr};"], warnings

    if isinstance(stmt, ast.Expr):
        expr = _emit_expr(stmt.value, config, warnings)
        return [f"{pad}let _ = {expr};"], warnings

    raise UnsupportedTwinOp(f"python.{type(stmt).__name__}", "")


def _emit_if(stmt: ast.If, config: TwinConfig, indent: int, warnings: List[str]) -> List[str]:
    pad = "    " * indent
    cond = _emit_expr(stmt.test, config, warnings)
    lines = [f"{pad}if {cond} {{"]
    inner, more = _emit_body(stmt.body, config)
    warnings.extend(more)
    lines.extend(inner)
    lines.append(f"{pad}}}")
    orelse = stmt.orelse
    if orelse:
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            inner_orelse = _emit_if(orelse[0], config, indent + 1, warnings)
            head = inner_orelse[0]
            if head.startswith("    " * (indent + 1) + "if "):
                head = "    " * indent + "} else " + head.lstrip()
                lines.append(head)
                lines.extend(inner_orelse[1:])
        else:
            lines.append(f"{pad}else {{")
            inner, more = _emit_body(orelse, config)
            warnings.extend(more)
            lines.extend(inner)
            lines.append(f"{pad}}}")
    return lines


def _emit_expr(node, config: TwinConfig, warnings: List[str]) -> str:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "true" if node.value else "false"
        if isinstance(node.value, int):
            return str(node.value)
        if isinstance(node.value, float):
            return repr(node.value)
        if isinstance(node.value, str):
            escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
            return f'String::from("{escaped}")'
        if node.value is None:
            warnings.append("python.None -> 0")
            return "0"
        raise UnsupportedTwinOp(f"python.const.{type(node.value).__name__}")

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.BinOp):
        left = _emit_expr(node.left, config, warnings)
        right = _emit_expr(node.right, config, warnings)
        op = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.Mod: "%", ast.FloorDiv: "/", ast.Pow: "pow",
        }.get(type(node.op))
        if op is None:
            raise UnsupportedTwinOp(f"python.binop.{type(node.op).__name__}")
        if op == "pow":
            return f"(({left}) as f64).powf(({right}) as f64)"
        return f"({left}) {op} ({right})"

    if isinstance(node, ast.Compare):
        if len(node.ops) != 1:
            raise UnsupportedTwinOp("python.compare.chain")
        op = {
            ast.Eq: "==", ast.NotEq: "!=",
            ast.Lt: "<", ast.LtE: "<=",
            ast.Gt: ">", ast.GtE: ">=",
        }.get(type(node.ops[0]))
        if op is None:
            raise UnsupportedTwinOp(f"python.compare.{type(node.ops[0]).__name__}")
        left = _emit_expr(node.left, config, warnings)
        right = _emit_expr(node.comparators[0], config, warnings)
        return f"({left}) {op} ({right})"

    if isinstance(node, ast.BoolOp):
        op = "&&" if isinstance(node.op, ast.And) else "||"
        return "(" + (f" {op} ".join(_emit_expr(v, config, warnings) for v in node.values)) + ")"

    if isinstance(node, ast.UnaryOp):
        operand = _emit_expr(node.operand, config, warnings)
        if isinstance(node.op, ast.USub):
            return f"-({operand})"
        if isinstance(node.op, ast.Not):
            return f"!({operand})"
        raise UnsupportedTwinOp(f"python.unop.{type(node.op).__name__}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise UnsupportedTwinOp("python.call.complex")
        args = [_emit_expr(a, config, warnings) for a in node.args]
        kwargs = [f"{kw.arg} = {_emit_expr(kw.value, config, warnings)}" for kw in node.keywords]
        params = ", ".join(args + kwargs)
        if node.func.id in _RUST_OPS:
            template = _RUST_OPS[node.func.id]
            if len(args) == 2:
                return template.format(a=args[0], b=args[1])
            if len(args) == 1:
                return template.format(a=args[0], b="0")
        return f"{node.func.id}({params})"

    if isinstance(node, ast.NameConstant):
        if node.value is None:
            return "0"
        if isinstance(node.value, bool):
            return "true" if node.value else "false"
        return str(node.value)

    raise UnsupportedTwinOp(f"python.expr.{type(node).__name__}")


def _infer_rust_type(node) -> str:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, int):
            return "i64"
        if isinstance(node.value, float):
            return "f64"
        if isinstance(node.value, str):
            return "String"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return "f64"
    return "i64"
