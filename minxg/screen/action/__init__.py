"""minxg.screen.action — input injection with fallback + retry.

Two surfaces:

- ActionEngine (class) — high-level dispatcher with retry + adaptation
- module-level helpers (tap / swipe / type_text / keyevent / back / home /
  long_press / swipe_up / swipe_down / tap_center_of_element) — thin
  re-exports of :mod:`input_engine` for backward compatibility.
"""
from __future__ import annotations
from .input_engine import (
    tap, swipe, type_text, keyevent, back, home,
    long_press, swipe_up, swipe_down, tap_center_of_element,
)
from .action_engine import ActionEngine

__all__ = [
    "ActionEngine",
    "tap", "swipe", "type_text", "keyevent", "back", "home",
    "long_press", "swipe_up", "swipe_down", "tap_center_of_element",
]
