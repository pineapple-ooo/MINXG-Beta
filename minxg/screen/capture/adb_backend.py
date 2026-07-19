"""minxg.screen.capture.adb_backend — ADB screencap + layout bridge.

Provides:
  adb_screencap(dest_path) → Path        — raw PNG pull
  adb_uiautomator_dump → str             — XML layout
  adb_device_connected() → bool           — quick reachability probe

Requires: adb on PATH, USB/wireless debug enabled, device connected.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional


def adb_device_connected(serial: str = "") -> bool:
    """Return True if at least one device is reachable (or specific one)."""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += ["devices"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        lines = r.stdout.strip().splitlines()
        # After "List of devices attached", any line with "device" (not "offline")
        return any("device" in ln and "offline" not in ln for ln in lines[1:])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def adb_screencap(dest_path: str, *, serial: str = "", rotate: int = 0) -> dict:
    """Grab the current screen as a PNG via adb screencap.

    Parameters
    ----------
    dest_path: str   — filesystem path to save the PNG
    serial: str      — optional device serial (USB/wireless)
    rotate: int      — 0=none, 90=cw, 180, 270 rotation (post-process)

    Returns: {path, width, height, format, source, timestamp, ok, error?}
    """
    out = {"source": "adb_screencap", "ok": False}
    if not adb_device_connected(serial):
        out["error"] = "no adb device connected"
        return out

    tmp = "/sdcard/_minxg_capture.png"
    cmd = ["adb", "-s", serial] if serial else ["adb"]
    # Pull to device storage first, then pull to host
    r1 = subprocess.run(cmd + ["shell", "screencap", "-p", tmp],
                        capture_output=True, text=True, timeout=15)
    if r1.returncode != 0:
        out["error"] = f"screencap shell failed: {r1.stderr[:200]}"
        return out

    # Pull to host
    dp = Path(dest_path)
    dp.parent.mkdir(parents=True, exist_ok=True)
    r2 = subprocess.run(cmd + ["pull", tmp, str(dp)],
                        capture_output=True, text=True, timeout=15)
    if r2.returncode != 0:
        out["error"] = f"adb pull failed: {r2.stderr[:200]}"
        # Cleanup remote
        subprocess.run(cmd + ["shell", "rm", tmp], capture_output=True)
        return out

    # Cleanup remote file
    subprocess.run(cmd + ["shell", "rm", tmp], capture_output=True)

    try:
        from PIL import Image
        img = Image.open(str(dp))
        w, h = img.size
        if rotate and rotate != 0:
            from PIL import Image
            ops = {90: Image.Transpose.ROTATE_270,
                   180: Image.Transpose.ROTATE_180,
                   270: Image.Transpose.ROTATE_90}
            img = img.transpose(ops.get(rotate, Image.Transpose.ROTATE_0))
            img.save(str(dp), "PNG")
        out.update(path=str(dp), width=w, height=h,
                   format="PNG", ok=True,
                   timestamp=time.time())
    except Exception as e:
        out["error"] = f"PIL open failed: {e}"
    return out


def adb_uiautomator_dump(*, serial: str = "", dest_xml: str = "") -> dict:
    """Dump the full accessibility layout via uiautomator.

    This is MORE powerful than a screenshot for AI understanding:
    it gives text labels, clickable flags, bounds, content-desc, class,
    resource-id — everything AI needs to PLAN actions without OCR.

    Returns: {xml, node_count, path, ok, error?}
    """
    out = {"source": "uiautomator", "ok": False}
    if not adb_device_connected(serial):
        out["error"] = "no adb device connected"
        return out

    tmp = "/sdcard/_minxg_uia.xml"
    cmd = ["adb", "-s", serial] if serial else ["adb"]
    r = subprocess.run(cmd + ["shell", "uiautomator", "dump", tmp],
                       capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or "UI hierchary dumped" not in r.stdout + r.stderr:
        out["error"] = f"uiautomator dump failed: {r.stderr[:200]}"
        return out

    dp = Path(dest_xml) if dest_xml else Path.home() / ".minxg" / "screen" / "layout" / "latest.xml"
    dp.parent.mkdir(parents=True, exist_ok=True)
    r2 = subprocess.run(cmd + ["pull", tmp, str(dp)],
                        capture_output=True, text=True, timeout=10)
    subprocess.run(cmd + ["shell", "rm", tmp], capture_output=True)

    if r2.returncode != 0:
        out["error"] = f"pull failed: {r2.stderr[:200]}"
        return out

    xml_text = dp.read_text(errors="replace")
    # Count node tags
    node_count = xml_text.count("<node")
    out.update(xml=xml_text[:50000], node_count=node_count,
               path=str(dp), ok=True, timestamp=time.time())
    return out


__all__ = ["adb_device_connected", "adb_screencap", "adb_uiautomator_dump"]
