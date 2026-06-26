"""test_experimental_features.py

`multiligua_cli.features` is the EXPERIMENTAL surface. These tests
guarantee the labeling does not regress: every public symbol here
must be (a) named in the documented list and (b) emit one warning
per call so the user is aware.
"""
import logging

import pytest

import multiligua_cli.features as feat


def test_module_docstring_marks_module_as_experimental():
    doc = (feat.__doc__ or "")
    assert "EXPERIMENTAL" in doc.upper()
    for name in [
        "Spinner", "context_usage_bar", "export_to_markdown",
        "share_to_gist", "welcome_animation", "SessionManager",
        "QuickFeedback", "SilentFeatures", "get_silent",
    ]:
        assert name in doc, f"feature {name!r} missing from module docstring"


def test_list_experimental_exports_includes_known_names():
    exports = set(feat.list_experimental_exports())
    for name in [
        "Spinner", "SessionManager", "SilentFeatures", "get_silent",
        "welcome_animation", "play_notification",
    ]:
        assert name in exports, f"{name!r} missing from list_experimental_exports()"


def test_get_silent_warns_and_emits_singleton(caplog):
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="features"):
        s1 = feat.get_silent()
        s2 = feat.get_silent()
        s3 = feat.get_silent()
    # singleton
    assert s1 is s2 is s3
    # warned at least once (warn-once dedup)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("EXPERIMENTAL" in m and "get_silent" in m for m in msgs)


def test_silent_features_method_warn_once(caplog):
    caplog.clear()
    s = feat.SilentFeatures()
    with caplog.at_level(logging.WARNING, logger="features"):
        s.disk_usage_report()
        s.disk_usage_report()
        s.disk_usage_report()
    disk_msgs = [r for r in caplog.records if "disk_usage_report" in r.getMessage()]
    assert len(disk_msgs) == 1, f"expected one warning, got {len(disk_msgs)}"


def test_check_updates_is_a_stub(caplog):
    caplog.clear()
    s = feat.SilentFeatures()
    with caplog.at_level(logging.WARNING, logger="features"):
        result = s.check_updates()
    assert result is None, "check_updates is a stub; must return None"


def test_dependency_health_returns_known_mods(caplog):
    caplog.clear()
    s = feat.SilentFeatures()
    with caplog.at_level(logging.WARNING, logger="features"):
        df = s.dependency_health()
    assert isinstance(df, dict)
    # rich and yaml are required by MINXG itself
    assert df.get("yaml") is True
    assert df.get("rich") is True
