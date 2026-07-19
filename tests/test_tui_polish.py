"""tests/test_tui_polish.py — terminal helpers from multiligua_cli.tui_polish."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force colour on for testing
os.environ["MINXG_COLOR"] = "1"

from multiligua_cli.tui_polish import (
    color, status_badge, syntax_highlight_python,
    tool_call_card, render_diff, progress,
)


def test_color_off_when_disabled(monkeypatch):
    import multiligua_cli.tui_polish as tp
    monkeypatch.setattr(tp, "_USE_COLOR", False)
    assert color("red", "hi") == "hi"
    monkeypatch.setattr(tp, "_USE_COLOR", True)


def test_color_red():
    c = color("red", "err")
    assert c.startswith("\x1b[31m")
    assert c.endswith("\x1b[0m")
    assert "err" in c


def test_status_badge_levels():
    assert "[OK]" in status_badge("ok", "done")
    assert "[!]" in status_badge("warn", "noise")
    assert "[X]" in status_badge("err", "boom")
    assert "[i]" in status_badge("info", "tip")


def test_syntax_highlight_keywords():
    line = "def foo(x): return x + 1  # n"
    out = syntax_highlight_python(line)
    assert "\x1b[35mdef" in out  # magenta for def/class
    assert "foo" in out
    assert "# n" in out  # gray comment preserved verbatim


def test_syntax_highlight_strings():
    line = 's = "hello"'
    out = syntax_highlight_python(line)
    assert "hello" in out


def test_tool_call_card_pending():
    card = tool_call_card("apk_plan", {"a": 1}, "pending", "")
    assert "apk_plan" in card
    assert "PENDING" in card


def test_tool_call_card_done():
    card = tool_call_card("apk_plan", {}, "done", "9 ops")
    assert "DONE" in card
    assert "9 ops" in card


def test_tool_call_card_error():
    card = tool_call_card("x", {}, "error", "boom")
    assert "ERROR" in card
    assert "boom" in card


def test_render_diff():
    text = "+++ a\n-bad\n+good\n@@ -1 +1 @@\n"
    out = render_diff(text)
    assert "good" in out
    assert "bad" in out


def test_progress_zero():
    p = progress("loading", 100, 0)
    assert "0%" in p
    assert "0/100" in p


def test_progress_full():
    p = progress("loading", 100, 100)
    assert "100%" in p
    assert "100/100" in p


def test_progress_half():
    p = progress("loading", 100, 50)
    assert "50%" in p


def test_color_with_unknown_palette():
    # falls through gracefully
    out = color("__not_a_palette__", "hi")
    assert "hi" in out