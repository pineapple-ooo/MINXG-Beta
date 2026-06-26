"""Extra coverage for minxg.twin — Python<->Rust AST twin compiler."""
import textwrap
import pytest
from minxg.twin import (
    python_to_rust,
    rust_to_python,
    UnsupportedTwinOp,
    TwinConfig,
)


def test_twin_module_imports_cleanly():
    import importlib
    import minxg.twin
    importlib.reload(minxg.twin)


def test_python_to_rust_if_else_chain():
    src = textwrap.dedent("""
        def classify(x: int) -> int:
            if x < 0:
                return -1
            elif x == 0:
                return 0
            else:
                return 1
    """).strip()
    result = python_to_rust(src)
    assert "if (x) < (0)" in result.source
    assert "} else if" in result.source or "else if" in result.source
    assert "return 1;" in result.source


def test_python_to_rust_for_range_with_start_and_stop():
    src = textwrap.dedent("""
        def count(from_val: int, to_val: int) -> int:
            s = 0
            for i in range(from_val, to_val):
                s = s + i
            return s
    """).strip()
    result = python_to_rust(src)
    assert "for i in from_val..to_val {" in result.source
    assert "let mut s: i64 = 0;" in result.source


def test_python_to_rust_while_loop():
    src = textwrap.dedent("""
        def countdown(n: int) -> int:
            i = n
            while i > 0:
                i = i - 1
            return i
    """).strip()
    result = python_to_rust(src)
    assert "while (i) > (0) {" in result.source
    # The emitter rewrites every assignment as `let mut`; inside the loop
    # the subtraction becomes `(i) - (1)`.
    assert "(i) - (1)" in result.source


def test_python_to_rust_rejects_unsupported_syntax():
    src = textwrap.dedent("""
        def bad():
            try:
                x = 1
            except Exception:
                pass
    """).strip()
    with pytest.raises(UnsupportedTwinOp):
        python_to_rust(src)


def test_rust_to_python_round_trips_arithmetic():
    rust_src = "pub fn calc(x: i64, y: i64) -> i64 { let a = x + y; let b = a * 2; return b - 1; }"
    result = rust_to_python(rust_src)
    assert "def calc(x: int, y: int):" in result.source
    assert "a = x + y" in result.source
    assert "b = a * 2" in result.source
    assert "return b - 1" in result.source


def test_rust_to_python_handles_bool_return_type():
    rust_src = "pub fn is_even(x: i64) -> bool { if x % 2 == 0 { return true; } return false; }"
    result = rust_to_python(rust_src)
    assert "def is_even(x: int):" in result.source or "def is_even(x: int) -> bool:" in result.source
    assert "True" in result.source
    assert "False" in result.source


def test_python_to_rust_with_function_name_override():
    src = textwrap.dedent("""
        def add(a: int, b: int) -> int:
            return a + b
    """).strip()
    cfg = TwinConfig(function_name="my_add")
    result = python_to_rust(src, config=cfg)
    assert "pub fn my_add(" in result.source
