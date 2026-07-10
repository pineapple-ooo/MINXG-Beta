"""minxg.screen.capture.mock_backend — synthetic screen for testing.

Generates a mock screenshot so the entire SPA pipeline can be exercised
without any real device hardware. The mock renders a simple Android-like
UI stub: status bar + content area + navigation bar, with labeled buttons.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

MOCK_W = 1080
MOCK_H = 2340


def mock_screencap(dest_path: str, *, width: int = 0, height: int = 0,
                   layout: str = "android_phone", seed_text: str = "MINXG AI Screen") -> dict:
    """Generate a synthetic screen image.

    Parameters
    ----------
    dest_path: str       — save path
    width, height: int   — override default 1080x2340
    layout: str          — 'android_phone' (1080x2340), 'tablet' (1200x1920), 'desktop' (1920x1080)
    seed_text: str       — text rendered on the mock screen so OCR has something to find

    Returns: {path, width, height, format, source, ok, timestamp}
    """
    out = {"source": "mock", "ok": False}
    w = width or MOCK_W
    h = height or MOCK_H

    if layout == "tablet":
        w, h = 1200, 1920
    elif layout == "desktop":
        w, h = 1920, 1080

    try:
        from PIL import Image, ImageDraw, ImageFont

        # Background — dark gray (Android dark theme)
        img = Image.new("RGB", (w, h), color="#121212")
        draw = ImageDraw.Draw(img)

        # Status bar (top)
        status_h = int(h * 0.04)
        draw.rectangle([0, 0, w, status_h], fill="#1E1E1E")
        draw.text((20, status_h // 4), "9:41  100%  WiFi  BT", fill="#888888")

        # App bar
        app_bar_h = int(h * 0.06)
        draw.rectangle([0, status_h, w, status_h + app_bar_h], fill="#2D2D2D")
        draw.text((20, status_h + app_bar_h // 3), seed_text, fill="#FFFFFF")

        # Content area with button-like rectangles
        content_top = status_h + app_bar_h
        content_bottom = h - int(h * 0.08)  # leave room for nav bar
        draw.rectangle([0, content_top, w, content_bottom], fill="#121212")

        # Mock UI elements — rectangles with labels
        btn_w = w - 80
        btn_h = 80
        gap = 30
        y = content_top + 40

        buttons = [
            ("Confirm", "#4CAF50"),
            ("Open Chat", "#2196F3"),
            ("Settings", "#757575"),
            ("View Docs", "#FF9800"),
        ]
        for label, color in buttons:
            draw.rectangle([40, y, 40 + btn_w, y + btn_h], fill=color, outline="#FFFFFF", width=2)
            draw.text((40 + btn_w // 2, y + btn_h // 2 - 15), label, fill="#FFFFFF")
            y += btn_h + gap

        # Input field
        draw.rectangle([40, y, 40 + btn_w, y + 60], fill="#2D2D2D", outline="#555555", width=1)
        draw.text((60, y + 18), "Type a command...", fill="#888888")

        # Nav bar (bottom)
        nav_h = int(h * 0.08)
        draw.rectangle([0, h - nav_h, w, h], fill="#1E1E1E")
        nav_items = ["Home", "Search", "Recent"]
        nw = w // len(nav_items)
        for i, item in enumerate(nav_items):
            draw.text((i * nw + nw // 2 - 40, h - nav_h + 15), item, fill="#888888")

        dp = Path(dest_path)
        dp.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(dp), "PNG")

        out.update(path=str(dp), width=w, height=h, format="PNG",
                   ok=True, timestamp=time.time())
    except Exception as e:
        out["error"] = f"mock_screencap failed: {e}"

    return out
