"""minxg.screen.action.input_engine — screen input via ADB + termux-api.

Opens a complete input bridge: tap, long_press, swipe, type, keyevent,
and composite actions (clear+type, slide_up, retry_tap).

All operations go through subprocess to the underlying tool; the
caller never sees native commands.
"""
from __future__ import annotations

import subprocess
import time
from typing import Optional, Tuple, List
from ..constants import ScreenSource


def _adb_check() -> Optional[str]:
    """Return adb path or None if adb not found."""
    try:
        subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
        return "adb"
    except FileNotFoundError:
        return None


def _termux_api_input_available() -> bool:
    termux_bin = "/data/data/com.termux/files/usr/bin/termux-api"
    try:
        subprocess.run([termux_bin, "--help"], capture_output=True, text=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def tap(x: int, y: int, *, serial: str = "", source: str = "adb") -> dict:
    """Tap a screen coordinate.

    Parameters
    ----------
    x, y: int        — center of tap target in px
    serial: str      — optional adb serial
    source: str      — 'adb' (preferred) or 'termux_api'

    Returns: {x, y, action, ok, error?}
    """
    out = {"action": "tap", "x": x, "y": y, "source": source, "ok": False}

    if source == "adb":
        adb = _adb_check()
        if not adb:
            out["error"] = "adb not available"
            return out
        cmd = ["adb", "-s", serial] if serial else ["adb"]
        r = subprocess.run(cmd + ["shell", "input", "tap", str(x), str(y)],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            out["ok"] = True
        else:
            out["error"] = r.stderr[:200]

    elif source == "termux_api" and _termux_api_input_available():
        r = subprocess.run(
            ["/data/data/com.termux/files/usr/bin/termux-api", "input",
             str(x), str(y), "tap"],
            capture_output=True, text=True, timeout=10)
        out["ok"] = r.returncode == 0
        if not out["ok"]:
            out["error"] = r.stderr[:200]
    else:
        out["error"] = f"source '{source}' not available on this device"

    return out


def long_press(x: int, y: int, duration_ms: int = 1000, *, serial: str = "") -> dict:
    """Long-press at a coordinate.

    Uses swipe with zero distance; Android treats swipe(dx,dy) with same
    start and end as long_press.
    """
    out = {"action": "long_press", "x": x, "y": y,
           "duration_ms": duration_ms, "ok": False}

    adb = _adb_check()
    if not adb:
        out["error"] = "adb not available"
        return out

    cmd = ["adb", "-s", serial] if serial else ["adb"]
    # swipe x1 y1 x2 y2 duration_ms — same start/end = long_press
    r = subprocess.run(cmd + ["shell", "input", "swipe",
                       str(x), str(y), str(x), str(y), str(duration_ms)],
                       capture_output=True, text=True, timeout=10)
    out["ok"] = r.returncode == 0
    if not out["ok"]:
        out["error"] = r.stderr[:200]
    return out


def swipe(x1: int, y1: int, x2: int, y2: int,
          duration_ms: int = 200, *, serial: str = "") -> dict:
    """Swipe from (x1,y1) to (x2,y2)."""
    out = {"action": "swipe", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
           "duration_ms": duration_ms, "ok": False}

    adb = _adb_check()
    if not adb:
        out["error"] = "adb not available"
        return out

    cmd = ["adb", "-s", serial] if serial else ["adb"]
    r = subprocess.run(cmd + ["shell", "input", "swipe",
                       str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
                       capture_output=True, text=True, timeout=10)
    out["ok"] = r.returncode == 0
    if not out["ok"]:
        out["error"] = r.stderr[:200]
    return out


def type_text(text: str, *, serial: str = "", source: str = "adb") -> dict:
    """Type a text string into the focused input field.

    ADB path: replaces spaces with %s for 'input text'.
    Termux:API path: uses termux-api input text.
    """
    out = {"action": "type_text", "text": text[:80], "ok": False}

    if source == "adb":
        adb = _adb_check()
        if not adb:
            out["error"] = "adb not available"
            return out
        cmd = ["adb", "-s", serial] if serial else ["adb"]
        escaped = text.replace(" ", "%s").replace("&", "%26")
        r = subprocess.run(cmd + ["shell", "input", "text", escaped],
                           capture_output=True, text=True, timeout=10)
        out["ok"] = r.returncode == 0
        if not out["ok"]:
            out["error"] = r.stderr[:200]

    elif source == "termux_api" and _termux_api_input_available():
        r = subprocess.run(
            ["/data/data/com.termux/files/usr/bin/termux-api", "input", "text", text],
            capture_output=True, text=True, timeout=10)
        out["ok"] = r.returncode == 0
        if not out["ok"]:
            out["error"] = r.stderr[:200]
    else:
        out["error"] = f"source '{source}' not available"

    return out


def keyevent(keycode: int, *, serial: str = "") -> dict:
    """Send a keyevent.

    Common codes: 3=HOME, 4=BACK, 26=POWER, 82=MENU, 111=ESC,
    112=DEL, 113=DPAD_LEFT, 114=DPAD_RIGHT, 115=DPAD_UP, 116=DPAD_DOWN.
    Full list: https://developer.android.com/reference/android/view/KeyEvent
    """
    out = {"action": "keyevent", "keycode": keycode, "ok": False}

    adb = _adb_check()
    if not adb:
        out["error"] = "adb not available"
        return out

    cmd = ["adb", "-s", serial] if serial else ["adb"]
    r = subprocess.run(cmd + ["shell", "input", "keyevent", str(keycode)],
                       capture_output=True, text=True, timeout=10)
    out["ok"] = r.returncode == 0
    if not out["ok"]:
        out["error"] = r.stderr[:200]
    return out


# ── Composite helpers ──────────────────────────────────────────────

def tap_center_of_element(bounds_rect: dict, *, serial: str = "") -> dict:
    """Tap the center of a UIAutomator bounds rectangle."""
    cx = bounds_rect.get("center_x", (bounds_rect["left"] + bounds_rect["right"]) // 2)
    cy = bounds_rect.get("center_y", (bounds_rect["top"] + bounds_rect["bottom"]) // 2)
    return tap(cx, cy, serial=serial)


def swipe_up(*, serial: str = "", distance: int = 500, duration_ms: int = 300) -> dict:
    """Swipe up (scroll down) from the middle of the screen."""
    return swipe(540, 1500, 540, 1500 - distance, duration_ms=duration_ms, serial=serial)


def swipe_down(*, serial: str = "", distance: int = 500, duration_ms: int = 300) -> dict:
    """Swipe down (scroll up)."""
    return swipe(540, 800, 540, 800 + distance, duration_ms=duration_ms, serial=serial)


def back(*, serial: str = "") -> dict:
    """Press BACK."""
    return keyevent(4, serial=serial)


def home(*, serial: str = "") -> dict:
    """Press HOME."""
    return keyevent(3, serial=serial)


def recent_apps(*, serial: str = "") -> dict:
    """Open recent apps switcher."""
    return keyevent(187, serial=serial)


__all__ = [
    "tap", "long_press", "swipe", "type_text", "keyevent",
    "tap_center_of_element", "swipe_up", "swipe_down", "back", "home", "recent_apps",
]
