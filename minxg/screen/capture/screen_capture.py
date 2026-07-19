"""minxg.screen.capture.screen_capture — Unified capture bridge.

Provides a single entry point for all screen capture operations:
- capture()      → screenshot (ADB/Termux/Camera/Mock)
- capture_uixml() → UIAutomator XML layout (ADB)
- capture_ocr()  → OCR text extraction (Tesseract)

Every method returns a dict with an "ok" key for error handling.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from minxg.screen.constants import (
    SCREEN_RAW,
    SCREEN_LAYOUT,
    SCREEN_OCR,
    ScreenSource,
    thresholds,
)


class ScreenCapture:
    """Unified screen capture bridge — delegates to the appropriate backend.

    Usage:
        sc = ScreenCapture()
        result = sc.capture()          # screenshot
        xml   = sc.capture_uixml()    # UIAutomator XML
        ocr   = sc.capture_ocr()      # OCR words + lines
    """

    # Path prefixes for each capture type
    RAW_DIR: Path = SCREEN_RAW
    LAYOUT_DIR: Path = SCREEN_LAYOUT
    OCR_DIR: Path = SCREEN_OCR

    def __init__(self, preferred_source: Optional[str] = None) -> None:
        self.preferred_source = preferred_source
        self._available: list = []
        self._detect_backends()

    # ── Backend detection ──────────────────────────────────────

    def _detect_backends(self) -> None:
        """Probe which capture backends are available on this device."""
        self._available = []

        # ADB
        try:
            from .adb_backend import adb_device_connected
            if adb_device_connected():
                self._available.append("adb")
        except Exception:
            pass

        # Termux:API
        try:
            from .termux_backend import termux_api_available
            if termux_api_available():
                self._available.append("termux")
        except Exception:
            pass

        # Camera
        try:
            from .camera_backend import camera_photo_available
            if camera_photo_available():
                self._available.append("camera")
        except Exception:
            pass

        # Mock is always available (no hardware needed)
        self._available.append("mock")

    def _pick_backend(self) -> str:
        """Choose the best available capture source."""
        if self.preferred_source and self.preferred_source in self._available:
            return self.preferred_source
        priority = ["adb", "termux", "camera", "mock"]
        for src in priority:
            if src in self._available:
                return src
        return "mock"

    def available_sources(self) -> list:
        """Return list of currently available capture sources."""
        return list(self._available)

    # ── Screenshot capture ─────────────────────────────────────

    def capture(self, source: str = "adb") -> Dict[str, Any]:
        """Capture the current screen as a PNG screenshot.

        Parameters
        ----------
        source : str — capture backend: "adb", "termux", "camera", or "mock"

        Returns
        -------
        dict with keys: path, w, h, format, bytes, source, ok, error?
        """
        ts = int(time.time() * 1000)
        src = source if source in self._available else self._pick_backend()

        try:
            if src == "adb":
                result = self._capture_adb(ts)
            elif src == "termux":
                result = self._capture_termux(ts)
            elif src == "camera":
                result = self._capture_camera(ts)
            else:
                result = self._capture_mock(ts)
        except Exception as e:
            return {"ok": False, "error": str(e), "source": src}

        # Ensure "ok" key is always present
        result.setdefault("ok", True)
        result.setdefault("source", src)
        if result.get("ok") and "bytes" not in result:
            try:
                p = Path(result.get("path", ""))
                if p.exists():
                    result["bytes"] = p.stat().st_size
            except Exception:
                pass
        return result

    def _capture_adb(self, ts: int) -> Dict[str, Any]:
        """Capture via adb shell screencap -p."""
        from .adb_backend import adb_screencap
        dest = str(self.RAW_DIR / f"adb_{ts}.png")
        frame = adb_screencap(dest)
        frame["source"] = "adb"
        return frame

    def _capture_termux(self, ts: int) -> Dict[str, Any]:
        """Capture via termux-api screencap."""
        from .termux_backend import termux_api_screencap
        dest = str(self.RAW_DIR / f"termux_{ts}.png")
        frame = termux_api_screencap(dest)
        frame["source"] = "termux"
        return frame

    def _capture_camera(self, ts: int) -> Dict[str, Any]:
        """Capture via termux-camera-photo (front camera approximation)."""
        from .camera_backend import camera_photo
        dest = str(self.RAW_DIR / f"camera_{ts}.jpg")
        frame = camera_photo(dest)
        frame["source"] = "camera"
        return frame

    def _capture_mock(self, ts: int) -> Dict[str, Any]:
        """Generate a synthetic gradient screenshot for testing."""
        from .mock_backend import mock_screencap
        dest = str(self.RAW_DIR / f"mock_{ts}.png")
        frame = mock_screencap(dest)
        frame["source"] = "mock"
        return frame

    # ── UIAutomator XML layout ────────────────────────────────

    def capture_uixml(self, source: str = "adb") -> Dict[str, Any]:
        """Capture the UIAutomator accessibility layout as XML.

        Parameters
        ----------
        source : str — currently only "adb" supports XML layout

        Returns
        -------
        dict with keys: xml, path, elements_count, ok, error?
        """
        ts = int(time.time() * 1000)

        if source == "adb" and "adb" in self._available:
            try:
                from .adb_backend import adb_uiautomator_dump
                xml_path = str(self.LAYOUT_DIR / f"uixml_{ts}.xml")
                result = adb_uiautomator_dump(dest_xml=xml_path)
                # Count nodes from the XML text
                if result.get("ok") and result.get("xml"):
                    node_count = result["xml"].count("<node")
                    result["elements_count"] = node_count
                else:
                    result["elements_count"] = 0
                result.setdefault("path", xml_path)
                return result
            except Exception as e:
                return {"ok": False, "error": str(e), "source": "adb"}

        # Non-ADB sources can't provide UIAutomator XML
        return {
            "ok": False,
            "error": f"UI XML capture not supported for source '{source}'. "
                     f"Use 'adb' for UIAutomator layout.",
            "source": source,
            "xml": "",
            "elements_count": 0,
        }

    # ── OCR extraction ─────────────────────────────────────────

    def capture_ocr(
        self,
        image_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run OCR on a screenshot to extract words and lines.

        If image_path is not provided, captures a fresh screenshot first
        via the best available backend.

        Parameters
        ----------
        image_path : str | None — path to PNG/JPEG; auto-captures if None
        **kwargs : forwarded to ocr_image (engine, lang, psm, etc.)

        Returns
        -------
        dict with keys: words, lines, timestamp, ok, error?
        """
        from ..ocr.ocr_pipeline import ocr_image, tesseract_available

        if not tesseract_available():
            return {
                "ok": False,
                "error": "tesseract not installed; run 'pkg install tesseract'",
                "words": [],
                "lines": [],
            }

        # Auto-capture if no image path given
        if not image_path:
            cap = self.capture(self._pick_backend())
            if not cap.get("ok"):
                return {
                    "ok": False,
                    "error": f"auto-capture failed: {cap.get('error', '?')}",
                    "words": [],
                    "lines": [],
                }
            image_path = cap.get("path", "")

        if not image_path or not Path(image_path).exists():
            return {
                "ok": False,
                "error": f"image not found: {image_path}",
                "words": [],
                "lines": [],
            }

        result = ocr_image(image_path, **kwargs)
        result.setdefault("timestamp", time.time())
        return result

    # ── Convenience: full pipeline capture ────────────────────

    def capture_all(self, source: str = "adb") -> Dict[str, Any]:
        """Capture screenshot + UIAutomator XML + OCR in one call.

        Returns a combined dict:
        {
            screenshot: {path, w, h, format, source, ok},
            uixml:      {xml, elements_count, path, ok},
            ocr:        {words, lines, timestamp, ok},
            ok:         bool
        }
        """
        screenshot = self.capture(source=source)
        uixml = self.capture_uixml(source=source)

        ocr_kwargs: Dict[str, Any] = {}
        if screenshot.get("ok") and screenshot.get("path"):
            ocr_kwargs["image_path"] = screenshot["path"]
        ocr = self.capture_ocr(**ocr_kwargs)

        all_ok = all(
            r.get("ok", False) for r in [screenshot, uixml, ocr]
        )

        return {
            "screenshot": screenshot,
            "uixml": uixml,
            "ocr": ocr,
            "ok": all_ok,
        }

    def __repr__(self) -> str:
        return (
            f"ScreenCapture("
            f"available={self._available}, "
            f"preferred={self.preferred_source or 'auto'})"
        )


__all__ = ["ScreenCapture"]