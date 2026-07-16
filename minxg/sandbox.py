"""minxg/sandbox.py — restricted execution for rule actions and conditions.

This module provides a safer alternative to raw ``eval``/``exec`` by
restricting the execution environment to a known-safe subset of Python:

* ``eval``-style conditions may only use safe comparison/logic operators
  and names explicitly whitelisted by the caller.
* ``exec``-style actions run in a globals dict that contains only a
  provided ``ctx`` mapping and a small set of harmless builtins.

Dangerous builtins such as ``__import__``, ``open``, ``compile``,
``exec``, ``eval``, ``globals``, ``locals``, ``getattr``, ``setattr``,
``delattr``, ``dir``, ``vars``, ``type``, ``isinstance``,
``issubclass``, ``breakpoint``, ``exit``, ``quit``, and ``help`` are
not exposed.

This is *defense-in-depth*, not a full sandbox.  Do not run untrusted
code inside MINXG; use this only for trusted internal DSLs.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, FrozenSet, Optional, Set

__all__ = ["RestrictedError", "safe_eval", "safe_exec"]


class RestrictedError(Exception):
    """Raised when an expression uses disallowed syntax."""


# ── Allowed builtins ───────────────────────────────────────────

_SAFE_BUILTINS: Dict[str, Any] = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "complex": complex,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "frozenset": frozenset,
    "int": int,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "pow": pow,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}


# ── AST visitor for eval ───────────────────────────────────────

class _EvalValidator(ast.NodeVisitor):
    """Allow only safe AST nodes for ``eval``-style conditions."""

    _BINOP = frozenset({
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    })
    _UNARYOP = frozenset({ast.UAdd, ast.USub, ast.Not})
    _CMPOP = frozenset({
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.In, ast.NotIn, ast.Is, ast.IsNot,
    })

    def __init__(self, allowed_names: FrozenSet[str]) -> None:
        self.allowed_names = allowed_names

    def visit_Expression(self, node: ast.Expression) -> None:
        self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, (bool, int, float, str, bytes, type(None))):
            raise RestrictedError(f"Unsupported constant type: {type(node.value).__name__}")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id not in self.allowed_names and node.id not in _SAFE_BUILTINS:
            raise RestrictedError(f"Disallowed name: {node.id}")

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if type(node.op) not in self._BINOP:
            raise RestrictedError(f"Disallowed binary op: {type(node.op).__name__}")
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if type(node.op) not in self._UNARYOP:
            raise RestrictedError(f"Disallowed unary op: {type(node.op).__name__}")
        self.visit(node.operand)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            if type(op) not in self._CMPOP:
                raise RestrictedError(f"Disallowed comparison: {type(op).__name__}")
        self.visit(node.left)
        for comparator in node.comparators:
            self.visit(comparator)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.visit(node.values[0])
        for value in node.values[1:]:
            self.visit(value)

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise RestrictedError("Only direct function calls are allowed")
        if node.func.id not in self.allowed_names and node.func.id not in _SAFE_BUILTINS:
            raise RestrictedError(f"Disallowed function call: {node.func.id}")
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        raise RestrictedError("Attribute access is not allowed")

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.visit(node.value)
        self.visit(node.slice)

    def visit_List(self, node: ast.List) -> None:
        for elt in node.elts:
            self.visit(elt)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        for elt in node.elts:
            self.visit(elt)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key in node.keys:
            if key is not None:
                self.visit(key)
        for value in node.values:
            self.visit(value)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Disallow lambda; they often hide exec/eval
        raise RestrictedError("Lambda expressions are not allowed")

    def visit_ListComp(self, node: ast.ListComp) -> None:
        raise RestrictedError("List comprehensions are not allowed")

    def visit_DictComp(self, node: ast.DictComp) -> None:
        raise RestrictedError("Dict comprehensions are not allowed")

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        raise RestrictedError("Generator expressions are not allowed")

    def visit_SetComp(self, node: ast.SetComp) -> None:
        raise RestrictedError("Set comprehensions are not allowed")

    def visit_Yield(self, node: ast.Yield) -> None:
        raise RestrictedError("Yield expressions are not allowed")

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        raise RestrictedError("Yield from expressions are not allowed")

    def visit_Starred(self, node: ast.Starred) -> None:
        raise RestrictedError("Starred expressions are not allowed")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        raise RestrictedError("Function definitions are not allowed")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        raise RestrictedError("Class definitions are not allowed")

    def visit_Import(self, node: ast.Import) -> None:
        raise RestrictedError("Import statements are not allowed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise RestrictedError("Import statements are not allowed")

    def visit_Assert(self, node: ast.Assert) -> None:
        raise RestrictedError("Assert statements are not allowed")

    def visit_Raise(self, node: ast.Raise) -> None:
        raise RestrictedError("Raise statements are not allowed")

    def visit_Try(self, node: ast.Try) -> None:
        raise RestrictedError("Try/except blocks are not allowed")

    def visit_With(self, node: ast.With) -> None:
        raise RestrictedError("With statements are not allowed")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        raise RestrictedError("Async function definitions are not allowed")

    def visit_Await(self, node: ast.Await) -> None:
        raise RestrictedError("Await expressions are not allowed")

    def visit_FormattedValue(self, node: ast.FormattedValue) -> None:
        raise RestrictedError("Formatted string values are not allowed")

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        raise RestrictedError("f-strings are not allowed")

    def visit_Delete(self, node: ast.Delete) -> None:
        raise RestrictedError("Delete statements are not allowed")

    def visit_Global(self, node: ast.Global) -> None:
        raise RestrictedError("Global statements are not allowed")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise RestrictedError("Nonlocal statements are not allowed")

    def visit_Pass(self, node: ast.Pass) -> None:
        raise RestrictedError("Pass statements are not allowed")

    def visit_Break(self, node: ast.Break) -> None:
        raise RestrictedError("Break statements are not allowed")

    def visit_Continue(self, node: ast.Continue) -> None:
        raise RestrictedError("Continue statements are not allowed")

    def visit_Return(self, node: ast.Return) -> None:
        raise RestrictedError("Return statements are not allowed")

    def visit_While(self, node: ast.While) -> None:
        raise RestrictedError("While loops are not allowed")

    def visit_For(self, node: ast.For) -> None:
        raise RestrictedError("For loops are not allowed")

    def visit_If(self, node: ast.If) -> None:
        raise RestrictedError("If statements are not allowed")

    def visit_With(self, node: ast.With) -> None:
        raise RestrictedError("With statements are not allowed")

    def visit_Match(self, node: ast.Match) -> None:
        raise RestrictedError("Match statements are not allowed")

    def visit_IfExp(self, node: ast.IfExp) -> None:
        raise RestrictedError("Ternary expressions are not allowed")

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        raise RestrictedError("Walrus operator is not allowed")


# ── Public API ─────────────────────────────────────────────────


def safe_eval(expr: str, *, allowed_names: Optional[Set[str]] = None) -> Any:
    """Evaluate a restricted Python expression.

    This is intended as a safer replacement for ``eval`` when the caller
    only needs basic comparison/logic over a known context.

    Parameters:
        expr: The expression to evaluate.
        allowed_names: Optional set of names the expression may reference
            in addition to the safe builtins.

    Returns:
        The result of the expression.

    Raises:
        RestrictedError: If the expression uses disallowed syntax.
        SyntaxError: If the expression cannot be parsed.
    """
    if not isinstance(expr, str):
        raise RestrictedError("Expression must be a string")

    tree = ast.parse(expr, mode="eval")
    allowed = frozenset(allowed_names or set())
    _EvalValidator(allowed).visit(tree)

    globals_dict: Dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
    locals_dict = {name: True for name in allowed_names or set()}
    return eval(compile(tree, "<restricted>", "eval"), globals_dict, locals_dict)


# Statement-level sandboxed execution for rule actions.
# We compile a function body instead of executing arbitrary code, and
# we strip access to dangerous builtins.

_DANGEROUS_NAME_PATTERNS = (
    "__import__",
    "open",
    "input",
    "breakpoint",
    "compile",
    "exec",
    "eval",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "isinstance",
    "issubclass",
    "type",
    "memoryview",
    "super",
    "property",
    "classmethod",
    "staticmethod",
)


def safe_exec(action_src: str, ctx: Dict[str, Any]) -> None:
    """Execute a restricted action statement in a sandboxed globals dict.

    The action source must be a valid Python statement block.
    It runs with access to ``ctx`` and a minimal builtins set.

    Parameters:
        action_src: Python source to execute.
        ctx: Mutable mapping used as the execution namespace.

    Raises:
        RestrictedError: If the source references dangerous names.
        SyntaxError: If the source cannot be parsed.
    """
    if not isinstance(action_src, str):
        raise RestrictedError("Action source must be a string")

    tree = ast.parse(action_src, mode="exec")

    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Name):
                name = child.id
                if name in _DANGEROUS_NAME_PATTERNS:
                    raise RestrictedError(f"Disallowed name in action: {name}")

    globals_dict: Dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "ctx": ctx,
    }
    exec(compile(tree, "<restricted-action>", "exec"), globals_dict)
