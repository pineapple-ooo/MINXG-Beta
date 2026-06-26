"""Normalize source in any supported language to an OperatorGraph."""
from __future__ import annotations
import ast
import re
from typing import List

from .graph import OperatorGraph, OperatorNode
from .languages import detect_language


def normalize(source: str, *, language: str = "") -> OperatorGraph:
    lang = language or detect_language(source)
    if lang == "python":
        return _normalise_python(source, lang)
    if lang == "rust":
        return _normalise_rust(source, lang)
    if lang == "javascript":
        return _normalise_javascript(source, lang)
    if lang == "go":
        return _normalise_go(source, lang)
    if lang == "shell":
        return _normalise_shell(source, lang)
    return OperatorGraph(source_language="unknown")


def _normalise_python(source: str, lang: str) -> OperatorGraph:
    graph = OperatorGraph(source_language=lang)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return graph
    scope: List[str] = []
    last_op = ""

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            op_id = ".".join(scope + [node.name]) if scope else node.name
            inputs = tuple(a.arg for a in node.args.args)
            graph.add_node(OperatorNode(
                op_id=op_id,
                inputs=inputs,
                output=op_id + ".result",
                params={},
                language=lang,
            ))
            if last_op:
                graph.add_edge(last_op, op_id)
            scope.append(node.name)
            self.generic_visit(node)
            scope.pop()

        def visit_Return(self, node: ast.Return):
            nonlocal last_op
            last_op = scope[-1] if scope else last_op

    Visitor().visit(tree)
    return graph


_CALL_RE = re.compile(r"([a-zA-Z_][\w]*)\s*\(")


def _normalise_rust(source: str, lang: str) -> OperatorGraph:
    graph = OperatorGraph(source_language=lang)
    scope: List[str] = []
    last_op = ""

    for raw in source.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"fn\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*(?:->\s*[^{]+)?\s*\{?", line)
        if m:
            name = m.group(1)
            params = [p.strip().split(":")[0].strip() for p in m.group(2).split(",") if p.strip()]
            op_id = ".".join(scope + [name]) if scope else name
            graph.add_node(OperatorNode(
                op_id=op_id,
                inputs=tuple(params),
                output=op_id + ".ret",
                language=lang,
            ))
            if last_op:
                graph.add_edge(last_op, op_id)
            last_op = op_id
        elif line.startswith("impl "):
            m2 = re.match(r"impl(?:<[^>]+>)?\s+([A-Za-z_][\w:<>,\s]*)", line)
            if m2:
                scope.append(m2.group(1).strip().split()[-1])
        elif line == "}":
            if scope:
                scope.pop()

    return graph


_JS_FN_RE = re.compile(r"function\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)")
_JS_ARROW_RE = re.compile(r"const\s+([a-zA-Z_]\w*)\s*=\s*\(([^)]*)\)\s*=>\s*\{?")


def _normalise_javascript(source: str, lang: str) -> OperatorGraph:
    graph = OperatorGraph(source_language=lang)
    last_op = ""
    funcs = _JS_FN_RE.findall(source) + _JS_ARROW_RE.findall(source)
    for name, params in funcs:
        inputs = tuple(p.strip() for p in params.split(",") if p.strip())
        node = OperatorNode(
            op_id=name,
            inputs=inputs,
            output=name + ".ret",
            language=lang,
        )
        graph.add_node(node)
        if last_op:
            graph.add_edge(last_op, name)
        last_op = name
    return graph


_GO_FN_RE = re.compile(r"func\s+(?:\([^)]*\)\s+)?([a-zA-Z_]\w*)\s*\(([^)]*)\)")


def _normalise_go(source: str, lang: str) -> OperatorGraph:
    graph = OperatorGraph(source_language=lang)
    last_op = ""
    for name, params in _GO_FN_RE.findall(source):
        inputs = tuple(p.strip().split()[-1].strip() for p in params.split(",") if p.strip())
        node = OperatorNode(
            op_id=name,
            inputs=inputs,
            output=name + ".out",
            language=lang,
        )
        graph.add_node(node)
        if last_op:
            graph.add_edge(last_op, name)
        last_op = name
    return graph


def _normalise_shell(source: str, lang: str) -> OperatorGraph:
    graph = OperatorGraph(source_language=lang)
    last_op = ""
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([a-zA-Z_]\w*)\s*\(\)\s*\{?", line)
        if m:
            name = m.group(1)
            node = OperatorNode(
                op_id=name,
                inputs=(),
                output=name + ".stdout",
                language=lang,
            )
            graph.add_node(node)
            if last_op:
                graph.add_edge(last_op, name)
            last_op = name
    return graph
