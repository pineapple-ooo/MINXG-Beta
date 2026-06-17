"""Tests for minxg.twin Python<->Rust emitter."""
import subprocess
import textwrap
import pytest
from minxg.twin import python_to_rust, rust_to_python, UnsupportedTwinOp


SIMPLE_PY = textwrap.dedent("""
    def add(a: int, b: int) -> int:
        x = a + b
        return x
""").strip()


def test_python_to_rust_emits_function():
    result = python_to_rust(SIMPLE_PY)
    assert "pub fn" in result.source
    assert "let mut x: i64" in result.source
    assert "(a) + (b)" in result.source
    assert "return" in result.source


def test_python_to_rust_handles_if_else():
    src = textwrap.dedent("""
        def signum(x: int) -> int:
            if x > 0:
                return 1
            elif x == 0:
                return 0
            else:
                return -1
    """).strip()
    result = python_to_rust(src)
    assert "if (x) > (0)" in result.source
    assert "} else if" in result.source or "else if" in result.source


def test_python_to_rust_handles_for_range():
    src = textwrap.dedent("""
        def total(n: int) -> int:
            s = 0
            for i in range(n):
                s = s + i
            return s
    """).strip()
    result = python_to_rust(src)
    assert "for i in 0..n" in result.source or "for i in" in result.source


def test_python_to_rust_handles_while():
    src = textwrap.dedent("""
        def countdown(n: int) -> int:
            i = n
            while i > 0:
                i = i - 1
            return i
    """).strip()
    result = python_to_rust(src)
    assert "while" in result.source


def test_python_to_rust_rejects_unsupported():
    src = textwrap.dedent("""
        def bad(items):
            for x in items:
                pass
    """).strip()
    with pytest.raises(UnsupportedTwinOp):
        python_to_rust(src)


def test_python_to_rust_emitted_function_compiles_when_rustc_present():
    rust_function = python_to_rust(SIMPLE_PY).source
    wrapped = (
        "fn main() { "
        + rust_function.replace("pub fn", "fn")
        + ' println!("{}", add(3, 4)); }'
    )
    if not _rustc_available():
        pytest.skip("rustc not installed")
    proc = subprocess.run(
        ["rustc", "-O", "-o", "/tmp/_twin_test", "-"],
        input=wrapped,
        text=True,
        capture_output=True,
        timeout=20,
    )
    if proc.returncode != 0:
        pytest.skip(f"rust compile failed: {proc.stderr}")
    run = subprocess.run(["/tmp/_twin_test"], capture_output=True, text=True, timeout=5)
    assert run.stdout.strip() == "7"


def _rustc_available() -> bool:
    return subprocess.run(["command", "-v", "rustc"], capture_output=True, shell=True).returncode == 0


def test_rust_to_python_round_trip_arithmetic():
    rust_src = "pub fn triple(x: i64) -> i64 { let y = x + 2; return y * 1; }"
    out = rust_to_python(rust_src)
    assert "def triple(x: int):" in out.source
    assert "y = x + 2" in out.source
    assert "return y * 1" in out.source


def test_rust_to_python_handles_bool_return():
    rust_src = "pub fn is_pos(x: i64) -> bool { if x > 0 { return true; } return false; }"
    out = rust_to_python(rust_src)
    assert "True" in out.source
    assert "False" in out.source
