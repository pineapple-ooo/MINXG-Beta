"""Tests for minxg.twin Python<->Rust emitter."""
import os
import subprocess
import tempfile
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
    if not _rustc_available():
        pytest.skip("rustc not installed")
    # Use a writable temp dir: Termux carts ``/tmp`` around as a
    # symlink that ``rustc`` cannot create its scratch subdirs under,
    # but ``tempfile.gettempdir()`` (the same one ``minxg.contracts.
    # runtime._exec.run`` uses) returns the platform-correct path.
    out_dir = tempfile.mkdtemp(prefix="minxg_twin_")
    out_path = os.path.join(out_dir, "twin_test")
    # The crate has to compile as a single file accepted by ``rustc
    # -``. Replace the *leading* ``pub fn`` so the inner function
    # becomes a free ``fn`` again, without disturbing later occurrences.
    wrapped = (
        "fn main() {\n"
        + rust_function.replace("pub fn add", "fn add", 1)
        + '\n    println!("{}", add(3, 4));\n}'
    )
    proc = subprocess.run(
        ["rustc", "-O", "-o", out_path, "-"],
        input=wrapped,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        # Hard-fail now that the emit logic preserves the original
        # function name: a skip here would mask a real regression.
        pytest.fail(
            "rustc failed to compile the emitted twin:\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    run = subprocess.run([out_path], capture_output=True, text=True, timeout=5)
    assert run.stdout.strip() == "7", (
        f"expected '7' from add(3,4), got stdout={run.stdout!r} "
        f"stderr={run.stderr!r}"
    )


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
