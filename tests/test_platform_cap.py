"""test_platform_cap.py — per-platform tool-budget."""
import os
import pytest

from multiling import platform_cap as pc


def test_detect_platform_key_returns_string():
    pk = pc.detect_platform_key()
    assert isinstance(pk, str)
    assert pk in {"android", "linux", "macos", "windows", "unknown"}


def test_cap_for_each_known_platform_positive():
    table = pc.platform_table()
    for k, c in table.items():
        assert c >= 100, f"unreasonable cap for {k}: {c}"


def test_android_cap_smaller_than_desktop():
    table = pc.platform_table()
    for desktop in ("linux", "macos", "windows"):
        assert table["android"] < table[desktop]
    assert table["android"] == 600


def test_env_override_is_honoured(monkeypatch):
    monkeypatch.setenv("MINXG_TOOL_CAP", "42")
    cap = pc.cap_for()
    assert cap == 42


def test_active_tools_subset_of_registry():
    pc.invalidate()
    active = pc.active_tools()
    try:
        from tools.registry import registry
        total = set(registry._tools.keys())
    except Exception:
        pytest.skip("registry not importable in this env")
    assert active.issubset(total)


def test_summary_has_required_keys():
    s = pc.summary()
    for k in ("platform", "cap", "active_count",
              "registered_count", "dropped_count"):
        assert k in s


def test_invalidate_drops_cache(monkeypatch):
    # Build a fresh cache.
    pc.invalidate()
    pc.active_tools()
    # Force a fallback computation path by patching the cap to 0.
    monkeypatch.setenv("MINXG_TOOL_CAP", "3")
    pc.invalidate()
    a = pc.active_tools()
    assert len(a) <= 3
