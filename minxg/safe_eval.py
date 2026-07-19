"""minxg/safe_eval.py — restricted math expression evaluator.

Replaces unsafe ``eval(...)`` calls with a safe AST-based evaluator that
only allows:
- numeric literals, unary +/-
- binary +, -, *, /, //, %, **
- comparisons: ==, !=, <, <=, >, >=
- boolean: and, or, not
- parentheses
- a whitelist of ``math`` names: sin, cos, tan, sqrt, log, exp, pow,
  abs, floor, ceil, round, asin, acos, atan, atan2, sinh, cosh, tanh,
  pi, e, inf, nan

No attribute access, no function calls other than the whitelist,
no comprehensions, no imports, no exec.
"""

from __future__ import annotations

import ast
import math
from typing import Any

_SAFE_MATH_NAMES = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sqrt": math.sqrt,
    "log": math.log,
    "exp": math.exp,
    "pow": pow,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": round,
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "nan": math.nan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
}


class SafeEvalError(Exception):
    """Raised when an expression uses disallowed syntax."""


def _eval_node(node: ast.AST, names: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise SafeEvalError(f"Unsupported constant type: {type(node.value).__name__}")
    if isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand, names)
        if isinstance(node.op, ast.UAdd):
            return +val
        if isinstance(node.op, ast.USub):
            return -val
        raise SafeEvalError(f"Unsupported unary op: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, names)
        right = _eval_node(node.right, names)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise SafeEvalError(f"Unsupported binary op: {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, names)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, names)
            if isinstance(op, ast.Eq):
                if not (left == right):
                    return False
            elif isinstance(op, ast.NotEq):
                if not (left != right):
                    return False
            elif isinstance(op, ast.Lt):
                if not (left < right):
                    return False
            elif isinstance(op, ast.LtE):
                if not (left <= right):
                    return False
            elif isinstance(op, ast.Gt):
                if not (left > right):
                    return False
            elif isinstance(op, ast.GtE):
                if not (left >= right):
                    return False
            else:
                raise SafeEvalError(f"Unsupported compare: {type(op).__name__}")
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, names) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise SafeEvalError(f"Unsupported bool op: {type(node.op).__name__}")
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        raise SafeEvalError(f"Disallowed name: {node.id}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise SafeEvalError("Only direct function calls are allowed")
        func_name = node.func.id
        if func_name not in names or not callable(names[func_name]):
            raise SafeEvalError(f"Disallowed callable: {func_name}")
        args = [_eval_node(a, names) for a in node.args]
        kwargs = {kw.arg: _eval_node(kw.value, names) for kw in node.keywords}
        return names[func_name](*args, **kwargs)
    raise SafeEvalError(f"Unsupported AST node: {type(node).__name__}")


def safe_eval_math(expr: str, extra_names: dict[str, Any] | None = None) -> Any:
    """Evaluate a math expression safely.

    >>> safe_eval_math("sin(pi/2)")
    1.0
    >>> safe_eval_math("2 ** 10")
    1024
    """
    if not isinstance(expr, str):
        raise SafeEvalError("Expression must be a string")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise SafeEvalError(f"Invalid expression: {exc}") from exc

    names = dict(_SAFE_MATH_NAMES)
    if extra_names:
        for key, value in extra_names.items():
            if not isinstance(key, str):
                raise SafeEvalError("extra_names keys must be strings")
            names[key] = value

    return _eval_node(tree, names)


def make_lambda(x_name: str, expr: str) -> Any:
    """Build a safe unary callable from a string expression.

    This replaces patterns like ``eval("lambda x: " + expr)``.

    The returned object is a real Python function, but its body only
    uses the allowed math operators and names.
    """
    if not x_name.isidentifier():
        raise SafeEvalError("Invalid variable name")

    def _fn(**kwargs: Any) -> Any:
        x = kwargs[x_name]
        return safe_eval_math(expr, {x_name: x})

    _fn.__name__ = f"<safe_lambda {x_name}: {expr}>"
    return _fn
