"""minxg/screen_cli.py — `minxg screen` verb handlers.

Each function takes the parsed argparse namespace and returns an int exit code.
Shared screen state (controller) is created lazily per call — doing it upfront
would block every `minxg screen describe` cold start with adb probing.
"""
from __future__ import annotations
import json
import os
import sys
import time
from typing import Any, Dict, Optional


# ── Lazy singleton ─────────────────────────────────────

_CTRL: Optional[Any] = None
_CAPTURE: Optional[Any] = None


def _get_ctrl():
    global _CTRL
    if _CTRL is None:
        try:
            from minxg.screen.screen_controller_v2 import ScreenControllerV2
            _CTRL = ScreenControllerV2(platform="android")
        except Exception as exc:
            print(f"screen: controller init failed: {exc}", file=sys.stderr)
            _CTRL = _FakeCtrl(exc)
    return _CTRL


def _get_capture():
    global _CAPTURE
    if _CAPTURE is None:
        try:
            from minxg.screen.capture.screen_capture import ScreenCapture
            _CAPTURE = ScreenCapture()
        except Exception as exc:
            _CAPTURE = _FakeCapture(exc)
    return _CAPTURE


class _FakeCtrl:
    def __init__(self, err):
        self._err = err
        self.platform = "unknown"
    def full_understand(self):
        return {"ok": False, "error": str(self._err), "elements": [], "description": ""}
    def tap(self, label="", x=0, y=0):
        return {"ok": False, "error": str(self._err)}
    def swipe_up(self, percent=50):
        return {"ok": False, "error": str(self._err)}
    def swipe_down(self, percent=50):
        return {"ok": False, "error": str(self._err)}
    def type_text(self, text, clear_first=True, label=""):
        return {"ok": False, "error": str(self._err)}
    def keyevent(self, keycode):
        return {"ok": False, "error": str(self._err)}
    def back(self):
        return {"ok": False, "error": str(self._err)}
    def home(self):
        return {"ok": False, "error": str(self._err)}
    def state_snapshot(self):
        return self.full_understand()


class _FakeCapture:
    def __init__(self, err):
        self._err = err
    def capture(self, source="adb"):
        return {"ok": False, "error": str(self._err)}
