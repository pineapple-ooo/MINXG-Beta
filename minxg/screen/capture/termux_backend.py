"""minxg.screen.capture.termux_backend — Termux:API screencap.

Uses the termux-api binary from the `termux-api` pkg to grab screenshots.
Requires the Termux:API Android companion app to be installed + running.
"""
from __future__ import annotations

import subprocess, time
from pathlib import Path


TERMUX_API_BIN = "/data/data/com.termux/files/usr/bin/termux-api"

def termux_api_available() -> bool:
    try:
        r = subprocess.run([TERMUX_API_BIN, "--help"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def termux_api_screencap(dest_path: str) -> dict:
    """Grab screen via 'termux-api screencap'.

    The termux-api pkg provides this via a socket to the companion app.
    Returns: {path, format, ok, error?, timestamp}
    """
    out = {"source": "termux_api", "ok": False}
    if not termux_api_available():
        out["error"] = "termux-api binary not on PATH; install termux-api pkg + companion app"
        return out

    dp = Path(dest_path)
    dp.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([TERMUX_API_BIN, "screencap", str(dp)],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not dp.exists():
        out["error"] = f"screencap failed: {r.stderr[:300]}"
        return out

    try:
        from PIL import Image
        img = Image.open(str(dp))
        out.update(path=str(dp), width=img.size[0], height=img.size[1],
                   format="PNG", ok=True, timestamp=time.time())
    except Exception as e:
        out["error"] = f"PIL error: {e}"
    return out
