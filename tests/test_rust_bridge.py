"""tests/test_rust_bridge.py — tests for Python ↔ Rust FFI bridge.

Tests skip gracefully if:
- The Rust shared library wasn't built (no `libminxg_rust.so` in target/release)
- The library exists but can't be dlopened (e.g. Termux external-storage namespace)

In both cases, the test reports "skipped" rather than failing — this is an
environmental limitation, not a code defect. CI logs will show the reason.
"""

import os
import sys
import pytest

import minxg.rust_bridge as bridge


def _try_load():
    """Try to instantiate RustLib; return (instance, error_message_or_None).

    Returns (None, reason) if the lib isn't loadable.
    """
    lib_path = (
        bridge._find_lib()
        if hasattr(bridge, "_find_lib")
        and bridge._find_lib() is not None
        else None
    )
    if lib_path is None:
        return None, "Rust shared library not built — run cd rust_core && cargo build --release"
    try:
        return bridge.RustLib.get(), None
    except OSError as e:
        return None, f"Rust lib at {lib_path} not dlopenable: {e}"
    except FileNotFoundError as e:
        return None, str(e)


_lib, _skip_reason = _try_load()


def _rust_available_or_skip():
    if _lib is None:
        pytest.skip(_skip_reason)


@pytest.mark.skipif(_lib is None, reason=_skip_reason or "")
class TestRustBridge:
    def test_version_string(self):
        v = _lib.version()
        assert v == "0.17.1"

    def test_math_operator_count(self):
        assert _lib.math_operator_count() == 42

    def test_logistic_map(self):
        # x_{n+1} = r * x * (1 - x), at fixed point x=0.5 with r=2.0
        x = bridge.logistic_map(0.5, 2.0)
        assert abs(x - 0.5) < 1e-10

    def test_lorenz_integrate_returns_3_components(self):
        # 100-step Euler on Lorenz, from (1, 0, 0); values stay bounded
        state = bridge.lorenz_integrate([1.0, 0.0, 0.0], 10.0, 28.0, 8.0 / 3.0, 0.001, 100)
        assert len(state) == 3
        assert all(isinstance(c, float) for c in state)
        # All components should remain finite
        assert all(c == c for c in state)  # NaN check


@pytest.mark.skipif(_lib is None, reason=_skip_reason or "")
class TestRustSingletonLifecycle:
    """Verify the RustLib singleton lifecycle is consistent."""

    def test_get_returns_same_instance(self):
        a = bridge.RustLib.get()
        b = bridge.RustLib.get()
        assert a is b

    def test_version_caching(self):
        rl = bridge.RustLib.get()
        v1 = rl.version()
        v2 = rl.version()
        assert v1 == v2 == "0.17.1"


def test_is_rust_available():
    """Always runs: just exercises the detection function."""
    val = bridge.is_rust_available()
    assert isinstance(val, bool)
    if val:
        assert _lib is not None, "is_rust_available() returned True but loadable failed"
    else:
        assert _lib is None, "is_rust_available() returned False but lib loaded"
