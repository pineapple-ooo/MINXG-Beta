"""minxg.screen.capture.camera_backend — termux-camera-photo fallback.

Captures the screen indirectly via the device camera. Front camera
gives a reasonable screen approximation; back camera is worse but
works in a pinch.
"""
from __future__ import annotations

import subprocess, time
from pathlib import Path


CAMERA_BIN = "/data/data/com.termux/files/usr/bin/termux-camera-photo"

def camera_photo_available() -> bool:
    try:
        subprocess.run([CAMERA_BIN, "--help"],
                       capture_output=True, text=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def camera_photo(dest_path: str, *, front: bool = True) -> dict:
    """Capture via termux-camera-photo.

    Parameters
    ----------
    dest_path: str   — where to save the JPEG
    front: bool      — True=front cam (default, better angle), False=back

    Returns: {path, width, height, format, ok, error?, timestamp}
    """
    out = {"source": "camera_photo", "ok": False}
    if not camera_photo_available():
        out["error"] = "termux-camera-photo not available; install termux-api pkg"
        return out

    dp = Path(dest_path)
    dp.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([CAMERA_BIN, str(dp)],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0 or not dp.exists():
        out["error"] = f"camera capture failed: {r.stderr[:300]}"
        return out

    try:
        from PIL import Image
        img = Image.open(str(dp))
        out.update(path=str(dp), width=img.size[0], height=img.size[1],
                   format="JPEG", ok=True, timestamp=time.time())
    except Exception as e:
        out["error"] = f"PIL error: {e}"
    return out
