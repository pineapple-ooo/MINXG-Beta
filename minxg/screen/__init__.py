"""minxg.screen — Screen Perception & Action (SPA) system.

This is the core capability that lets AI agents SEE, UNDERSTAND, and ACT
on a device screen. It combines multiple capture backends, OCR, structural
layout analysis, and input actions into a unified loop.

Quick start:
  from minxg.screen import ScreenController

  # Auto-detect available backend and capture screen
  ctrl = ScreenController()
  frame = ctrl.capture()

  # Understand what's on screen
  understanding = ctrl.understand(frame)
  print(understanding["description"])

  # Act: tap a button by text
  ctrl.tap("Confirm")

  # Full autonomous loop: capture → understand → act → verify
  result = ctrl.autonomous_step("Press the green Confirm button")

Architecture:
  capture/        — ADB, Termux:API, Camera, Mock backends
  action/         — tap, swipe, type, keyevent (via ADB/termux-api)
  ocr/            — Tesseract OCR → word/line-level structured text
  perception/     — UIAutomator XML + OCR merge → screen understanding
  controller/     — ScreenController: capture→understand→act closure
"""
from __future__ import annotations

from .capture import adb_screencap, adb_uiautomator_dump, mock_screencap
from .action import tap, swipe, type_text, keyevent
from .ocr import ocr_image, tesseract_available
from .perception import build_screen_description, find_tappable_elements, parse_uiautomator_xml
from .controller.screen_controller import ScreenController

__all__ = [
    # Capture
    "adb_screencap", "adb_uiautomator_dump", "mock_screencap",
    # Action
    "tap", "swipe", "type_text", "keyevent",
    # OCR
    "ocr_image", "tesseract_available",
    # Perception
    "build_screen_description", "find_tappable_elements", "parse_uiautomator_xml",
    # Controller
    "ScreenController",
]

__version__ = "1.0.0"

# Screen module is auto-discovered via minxg/base.py WorkerRegistry and
# the five_pillars/dispatch/screen_tools.py ScreenWorker — no manual
# registration needed. The old register_screen_commands hook was removed
# in platform_registry v0.16.0 platform consolidation.
