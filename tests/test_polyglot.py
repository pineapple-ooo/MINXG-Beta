"""Tests for minxg.polyglot."""
import pytest
from minxg.polyglot import (
    OperatorGraph, OperatorNode, OperatorEdge,
    normalize, detect_language, detect_language_from_path,
)
from pathlib import Path


PY_SOURCE = """
def add(a, b):
    return a + b

def multiply_by_two(x):
    return add(x, x)
"""


RUST_SOURCE = """
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}

impl Calculator {
    fn new() -> Calculator { Calculator }
}
"""


JS_SOURCE = """
function fetchUser(id) {}
const saveUser = (user) => {};
function deleteUser(id) {}
"""


GO_SOURCE = """
package demo

func Add(a int, b int) int { return a + b }
func (c *Calc) Mul(a, b int) int { return a * b }
"""


SH_SOURCE = """
#!/bin/bash
build() {
    echo "build"
}
test() {
    echo "test"
}
"""


def test_detect_python():
    assert detect_language(PY_SOURCE) == "python"


def test_detect_rust():
    assert detect_language(RUST_SOURCE) == "rust"


def test_detect_javascript():
    assert detect_language(JS_SOURCE) == "javascript"


def test_detect_go():
    assert detect_language(GO_SOURCE) == "go"


def test_detect_shell():
    assert detect_language(SH_SOURCE) == "shell"


def test_detect_from_path(tmp_path: Path):
    fp = tmp_path / "x.py"
    fp.write_text(PY_SOURCE)
    assert detect_language_from_path(fp) == "python"


def test_python_normaliser_emits_call_chain():
    graph = normalize(PY_SOURCE)
    names = {n.op_id for n in graph.nodes}
    assert "add" in names and "multiply_by_two" in names
    order = [n.op_id for n in graph.topological_order()]
    assert order.index("add") < order.index("multiply_by_two")


def test_rust_normaliser_finds_fns_and_impl():
    graph = normalize(RUST_SOURCE)
    names = {n.op_id for n in graph.nodes}
    assert any("add" in n for n in names)


def test_javascript_normaliser_finds_arrow_and_function():
    graph = normalize(JS_SOURCE)
    names = {n.op_id for n in graph.nodes}
    assert "fetchUser" in names and "saveUser" in names


def test_go_normaliser_finds_methods():
    graph = normalize(GO_SOURCE)
    names = {n.op_id for n in graph.nodes}
    assert "Add" in names


def test_shell_normaliser_finds_functions():
    graph = normalize(SH_SOURCE)
    names = {n.op_id for n in graph.nodes}
    assert "build" in names and "test" in names


def test_topological_order_respects_dependencies():
    g = OperatorGraph()
    g.add_node(OperatorNode(op_id="a"))
    g.add_node(OperatorNode(op_id="b"))
    g.add_node(OperatorNode(op_id="c"))
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    order = [n.op_id for n in g.topological_order()]
    assert order == ["a", "b", "c"]
