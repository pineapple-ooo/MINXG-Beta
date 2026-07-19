"""tests/test_wizard_smart.py — smart wizard module."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from multiligua_cli.wizard_smart import (
    schema, smart_suggest, default_for, skill_discover, progress_label,
)


def test_schema_returns_5_fields():
    s = schema()
    assert len(s) == 5
    assert any(k == "provider" for k, _ in s)


def test_smart_suggest_first_missing():
    res = smart_suggest({})
    assert res is not None
    assert res[0] == "provider"


def test_smart_suggest_skips_filled():
    cfg = {
        "provider": "openai", "model": "gpt-4o-mini",
        "api_key": "x", "base_url": "https://api.openai.com/v1",
        "language": "en",
    }
    assert smart_suggest(cfg) is None


def test_smart_suggest_returns_one_at_a_time():
    res = smart_suggest({"provider": "anthropic"})
    assert res[0] == "model"


def test_default_for_provider_falls_back():
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]
    assert default_for("provider") == "openai"


def test_default_for_base_url_anthropic():
    assert "anthropic" in default_for("base_url", {"provider": "anthropic"})


def test_default_for_language():
    os.environ["LANG"] = "zh_CN.UTF-8"
    assert default_for("language") == "zh"


def test_progress_label():
    s = progress_label(2, 4, "Step")
    assert "[==--=]" not in s
    assert "50%" in s


def test_progress_label_edges():
    assert "0%" in progress_label(0, 4)
    assert "100%" in progress_label(4, 4)


def test_skill_discover_returns_list():
    out = skill_discover()
    assert isinstance(out, list)