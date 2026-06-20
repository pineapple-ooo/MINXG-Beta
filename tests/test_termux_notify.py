"""test_termux_notify.py — TermuxAPI helper is silent and safe elsewhere."""
import os
import pytest

from src.ai.notify import termux


def test_not_available_when_termux_env_missing(monkeypatch):
    for k in ("TERMUX_VERSION", "ZERO_TERMUX", "ZEROTERMUX_VERSION"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(termux.shutil, "which", lambda _: None)
    assert not termux.is_available()
    # All helpers must return False (no exceptions) outside Termux.
    assert termux.send("t", "b") is False
    assert termux.toast("hi") is False
    assert termux.vibrate(150) is False
    assert termux.notify_task_completed() is False


def test_beep_writes_bell_regardless_of_platform():
    import io
    import sys
    saved = sys.stdout
    try:
        buf = io.StringIO()
        sys.stdout = buf
        result = termux.beep()
        sys.stdout = saved
    except Exception:
        sys.stdout = saved
        raise
    assert result is True
    assert "\a" in buf.getvalue()


def test_send_does_not_raise_under_bad_env(monkeypatch):
    # No Termux env, no termux-notification on PATH.
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setattr(termux.shutil, "which", lambda _: None)
    # Should swallow everything and return False.
    assert termux.send("anything",
                      "with weird chars \x00 \xff",
                      priority="bogus",
                      channel="x", vibrate=(1, 2),
                      sound=True, sticky=True,
                      id="42", content_type="image",
                      action="weird") is False
