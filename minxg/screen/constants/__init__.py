"""minxg.screen.constants — shared types, paths, and thresholds.

ScreenSource — where the screenshot comes from
      ADB               — 'adb shell screencap' (requires ADB connection)
      UIAAUTOMATOR      — 'adb shell uiautomator dump' → XML layout
      TERMUX_API        — 'termux-api screencap' (needs companion app)
      CAMERA_PHOTO      — 'termux-camera-photo' (front cam, approx)
      CAMERA_BACK       — 'termux-camera-photo --stop-motion' (back cam)
      MOCK               — in-memory synthetic screen (for testing / demo)

PILFormats — image format constants bridging capture, OCR, and perception.
OcrEngine — lightweight enum instead of tightly coupled tesseract import.
LayoutFormat — output types from the UIAutomator XML dump.

thresholds — numeric fine-tuning knobs for perception (all floats).
snapshot_paths — per-source cache directories; each backend writes here.
"""
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Optional


# ── Capture source ────────────────────────────────────────────────

class ScreenSource(str, Enum):
    """How the screen frame is acquired."""

    ADB = "adb"
    """adb shell screencap -p → PNG bytes"""

    UIAUTOMATOR = "uiautomator"
    """adb shell uiautomator dump → XML node tree (STRUCTURAL, not pixel)"""

    TERMUX_API = "termux_api"
    """termux-api screencap → JPEG/PNG (needs com.termux.api app)"""

    CAMERA_PHOTO = "camera_photo"
    """Front-camera snapshot — rough screen approximation"""

    CAMERA_BACK = "camera_back"
    """Back-camera snapshot — even more approximate"""

    MOCK = "mock"
    """Synthetic gradient/blank frame — for testing without hardware"""


# ── Image format ───────────────────────────────────────────────────

class PILFormats:
    """Format strings accepted by Pillow.Image.save()."""

    PNG = "PNG"
    JPEG = "JPEG"
    TIEF = "TIFF"
    BMP = "BMP"
    WEBP = "WEBP"


# ── OCR engine ─────────────────────────────────────────────────────

class OcrEngine(str, Enum):
    """Tesseract-backed OCR pipeline.

    LSTM gives higher accuracy at the cost of speed.
    TESSERACT_ONLY is the original engine — faster but less robust.
    RAW_LINE gives raw text without any layout grouping.
    """

    DEFAULT = "default"            # LSTM or best available
    LSTM = "lstm"                  # force LSTM engine
    TESSERACT_ONLY = "tesseract_only"  # OCR-A style, fast
    RAW_LINE = "raw_line"          # one tesseract line per result
    BOX = "box"                    # include bounding boxes per word


# ── Layout format ──────────────────────────────────────────────────

class LayoutFormat(str, Enum):
    """Output format from UIAutomator XML dumps."""

    XML = "xml"         # raw uiautomator XML (default)
    JSON = "json"       # transformed into structured dicts
    TREE = "tree"       # indented ASCII tree for human reading
    FLAT = "flat"       # flat list of {bounds, text, class, res_id}


# ── Thresholds ─────────────────────────────────────────────────────

thresholds = {
    "ocr_confidence_min": 60,       # below this % → discard word
    "element_min_words": 2,         # fewer words → not a useful UI element
    "layout_merge_distance": 20,    # px — bounding box gap to treat as same element
    "swipe_duration_ms": 200,       # base swipe time
    "tap_delay_ms": 100,            # min ms between taps
    "screenshot_max_files": 10,     # rotation count for cache
    "mock_width": 1080,
    "mock_height": 2340,
}


# ── Paths ───────────────────────────────────────────────────────────

def _screen_cache_dir() -> Path:
    root = Path.home() / ".minxg" / "screen"
    root.mkdir(parents=True, exist_ok=True)
    return root


SCREEN_CACHE = _screen_cache_dir()
SCREEN_RAW = SCREEN_CACHE / "raw"
SCREEN_OCR = SCREEN_CACHE / "ocr"
SCREEN_LAYOUT = SCREEN_CACHE / "layout"
SCREEN_OVERLAY = SCREEN_CACHE / "overlay"

for p in (SCREEN_RAW, SCREEN_OCR, SCREEN_LAYOUT, SCREEN_OVERLAY):
    p.mkdir(parents=True, exist_ok=True)


# ── Helpers ────────────────────────────────────────────────────────

def bounds_to_rect(bounds_str: str) -> Optional[dict]:
    """Parse Android UIAutomator bounds=""[left,top][right,bottom]"" to dict.

    Returns None if parsing fails; caller should handle gracefully.
    """
    import re
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not m:
        return None
    left, top, right, bottom = (int(g) for g in m.groups())
    return {
        "left": left, "top": top,
        "right": right, "bottom": bottom,
        "center_x": (left + right) // 2,
        "center_y": (top + bottom) // 2,
        "width": right - left,
        "height": bottom - top,
        "area": (right - left) * (bottom - top),
    }


__all__ = [
    "ScreenSource", "PILFormats", "OcrEngine", "LayoutFormat",
    "thresholds", "SCREEN_CACHE", "SCREEN_RAW", "SCREEN_OCR",
    "SCREEN_LAYOUT", "SCREEN_OVERLAY", "bounds_to_rect",
]
