"""minxg.five_pillars.dispatch.screen_tools — AI worker exposing screen actions as tools.

Wraps ScreenControllerV2 as a BaseWorker so the AI can discover and call
all screen operations via the standard tool-call interface.

Tool categories:
- screen_describe  — human-readable screen description + element count
- screen_find      — search elements by text/class/bounds with coordinates
- screen_tap       — tap by label or coordinates
- screen_swipe     — swipe in a direction (up/down/left/right)
- screen_type      — type text into focused input field
- screen_key       — press system keys (BACK/HOME/ENTER/etc.)
- screen_act       — high-level "do X" with automatic element resolution
- screen_state     — get current screen state as structured dict
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool
from minxg.screen.capture.screen_capture import ScreenCapture
from minxg.screen.screen_controller_v2 import ScreenControllerV2
from minxg.five_pillars.dispatch.platform_registry import is_adb_available

log = logging.getLogger("minxg.five_pillars.dispatch.screen_tools")


def _adb_not_available_error() -> Dict[str, Any]:
    """Return a structured error dict when ADB is not reachable.

    Used by action tools (tap/swipe/type/key) that REQUIRE ADB; the
    describe/find/state tools still work on MOCK when ADB is absent.
    """
    return {
        "status": "error",
        "ok": False,
        "error": "adb not available — check device connection and USB debugging",
    }


def _is_adb_available() -> bool:
    """Quick check: is ADB on PATH and a device connected?"""
    try:
        return is_adb_available()
    except Exception:
        # Fallback: try running adb directly
        try:
            r = subprocess.run(
                ["adb", "devices"],
                capture_output=True, text=True, timeout=5,
            )
            lines = r.stdout.strip().splitlines()
            return any("device" in ln and "offline" not in ln for ln in lines[1:])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


def _adb_required_or_error() -> Optional[Dict[str, Any]]:
    """For action tools only. Returns error dict if adb missing, else None."""
    if not _is_adb_available():
        return _adb_not_available_error()
    return None


class ScreenWorker(BaseWorker):
    """AI-accessible screen perception and action worker.

    worker_id : "screen"
    version   : "0.1.0"

    All tools have call_budget=25 (screen actions are expensive — each
    involves a subprocess call to ADB or Tesseract).
    """

    worker_id: str = "screen"
    version: str = "0.1.0"

    def __init__(self) -> None:
        self._ctrl: Optional[ScreenControllerV2] = None
        super().__init__()

    def _get_controller(self) -> ScreenControllerV2:
        """Lazy-create ScreenControllerV2 on first use."""
        if self._ctrl is None:
            from minxg.screen.constants import ScreenSource
            # Only force MOCK if ADB is not available
            if _is_adb_available():
                preferred = ScreenSource.ADB
            else:
                preferred = ScreenSource.MOCK
            self._ctrl = ScreenControllerV2(
                platform="android",
                preferred_source=preferred,
                verbose=False,
            )
        return self._ctrl

    # ── Tool: screen_describe ─────────────────────────────────

    @tool(
        description="Get a human-readable description of the current screen, "
                    "including element count and tappable items.",
        category="screen",
        call_budget=25,
    )
    def screen_describe(self) -> Dict[str, Any]:
        """Describe what's on the current screen.

        Returns a human-readable description plus element statistics.

        Works on MOCK when ADB is unavailable (returns whatever the active
        capture backend produced; no live action is taken).
        """
        try:
            ctrl = self._get_controller()
            state = ctrl.full_understand()

            if not state.get("ok"):
                return {
                    "status": "error",
                    "ok": False,
                    "error": state.get("error", "understanding failed"),
                }

            return {
                "status": "success",
                "ok": True,
                "description": state.get("description", ""),
                "n_elements": state.get("n_elements", 0),
                "n_clickable": state.get("n_clickable", 0),
                "screenshot_path": state.get("screenshot_path", ""),
            }
        except Exception as e:
            log.error("screen_describe failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_find ──────────────────────────────────────

    @tool(
        description="Search for screen elements by text, class name, or bounding box. "
                    "Returns matching elements with coordinates and match scores.",
        category="screen",
        call_budget=25,
    )
    def screen_find(
        self,
        text: str = "",
        class_name: str = "",
        left: int = 0,
        top: int = 0,
        right: int = 0,
        bottom: int = 0,
        clickable_only: bool = False,
        fuzzy: bool = True,
    ) -> Dict[str, Any]:
        """Find elements on the current screen.

        Search modes (use at most one):
        - text      : fuzzy or exact text match against element labels
        - class_name : match Android class (e.g. "Button", "EditText")
        - left/top/right/bottom : find elements in a bounding box region

        Returns matching elements with center coordinates. Works on MOCK
        when ADB is unavailable; queries ElementIndex only.
        """
        try:
            ctrl = self._get_controller()
            state = ctrl.full_understand()

            if not state.get("ok"):
                return {
                    "status": "error",
                    "ok": False,
                    "error": state.get("error", "understanding failed"),
                }

            index = state.get("element_index")
            if index is None:
                return {
                    "status": "error",
                    "ok": False,
                    "error": "no element index available",
                }

            results: List[Dict] = []

            # Text search
            if text:
                hits = index.find_by_text(
                    text, fuzzy=fuzzy, clickable_only=clickable_only
                )
                for h in hits:
                    results.append(self._format_element(h, "text"))
                return {
                    "status": "success",
                    "ok": True,
                    "query": {"text": text, "fuzzy": fuzzy},
                    "n_matches": len(results),
                    "matches": results,
                }

            # Class search
            if class_name:
                hits = index.find_by_class(class_name)
                for h in hits:
                    results.append(self._format_element(h, "class"))
                return {
                    "status": "success",
                    "ok": True,
                    "query": {"class_name": class_name},
                    "n_matches": len(results),
                    "matches": results,
                }

            # Bounds search
            if left or top or right or bottom:
                hits = index.find_in_bounds(left, top, right, bottom)
                for h in hits:
                    results.append(self._format_element(h, "bounds"))
                return {
                    "status": "success",
                    "ok": True,
                    "query": {"bounds": [left, top, right, bottom]},
                    "n_matches": len(results),
                    "matches": results,
                }

            # No search criteria — return clickable elements
            if clickable_only:
                hits = index.find_clickable()
                for h in hits:
                    results.append(self._format_element(h, "clickable"))
                return {
                    "status": "success",
                    "ok": True,
                    "query": {"clickable_only": True},
                    "n_matches": len(results),
                    "matches": results,
                }

            return {
                "status": "error",
                "ok": False,
                "error": "provide at least one search criterion: text, "
                         "class_name, or bounds",
                "available_sources": ctrl._capture.available_sources(),
            }
        except Exception as e:
            log.error("screen_find failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_tap ───────────────────────────────────────

    @tool(
        description="Tap on a screen element by label text or by coordinates. "
                    "Uses ElementIndex for label resolution with fuzzy matching.",
        category="screen",
        call_budget=25,
    )
    def screen_tap(
        self,
        label: str = "",
        x: int = 0,
        y: int = 0,
    ) -> Dict[str, Any]:
        """Tap on screen.

        Two modes:
        - label="Submit" → resolve label to coordinates via ElementIndex
        - x=540, y=1200 → tap at absolute coordinates
        """
        if not _is_adb_available():
            return _adb_not_available_error()

        try:
            ctrl = self._get_controller()
            result = ctrl.tap(label=label, x=x, y=y)

            # Normalize output to structured format
            ok = result.get("ok", result.get("status") == "ok")
            if ok:
                return {
                    "status": "success",
                    "ok": True,
                    "detail": f"tapped '{label or f'({x},{y})'} successfully",
                    "action_result": result,
                }
            return {
                "status": "error",
                "ok": False,
                "detail": result.get("error", "tap failed"),
                "action_result": result,
            }
        except Exception as e:
            log.error("screen_tap failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_swipe ─────────────────────────────────────

    @tool(
        description="Swipe the screen in a direction: up, down, left, right, "
                    "or custom (specify start/end coordinates).",
        category="screen",
        call_budget=25,
    )
    def screen_swipe(
        self,
        direction: str = "up",
        percent: int = 50,
        x: int = 0,
        y: int = 0,
        end_x: int = 0,
        end_y: int = 0,
    ) -> Dict[str, Any]:
        """Swipe the screen.

        Parameters:
        - direction: "up", "down", "left", "right"
        - percent: swipe distance percentage (for up/down)
        - x/y/end_x/end_y: custom swipe coordinates (use instead of direction)
        """
        if not _is_adb_available():
            return _adb_not_available_error()

        try:
            ctrl = self._get_controller()

            if x and y and end_x and end_y:
                # Custom swipe
                result = ctrl._engine.swipe(
                    x=x, y=y, dx=end_x - x, dy=end_y - y,
                    duration_ms=300,
                    description=f"custom swipe ({x},{y})→({end_x},{end_y})",
                )
            else:
                result = ctrl.swipe(direction=direction, percent=percent)

            ok = result.get("ok", result.get("status") == "ok")
            if ok:
                return {
                    "status": "success",
                    "ok": True,
                    "detail": f"swiped {direction} ({percent}%)",
                    "action_result": result,
                }
            return {
                "status": "error",
                "ok": False,
                "detail": result.get("error", "swipe failed"),
                "action_result": result,
            }
        except Exception as e:
            log.error("screen_swipe failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_type ──────────────────────────────────────

    @tool(
        description="Type text into the current focused input field. "
                    "Optionally specify a label to focus a specific field first.",
        category="screen",
        call_budget=25,
    )
    def screen_type(self, text: str, label: str = "") -> Dict[str, Any]:
        """Type text into an input field.

        If label is given, first tap/focus that input field via ElementIndex.
        Then type the text.
        """
        if not _is_adb_available():
            return _adb_not_available_error()

        try:
            ctrl = self._get_controller()
            result = ctrl.type_text(text=text, label=label)

            ok = result.get("ok", result.get("status") == "ok")
            if ok:
                return {
                    "status": "success",
                    "ok": True,
                    "detail": f"typed '{text[:40]}'" + ("..." if len(text) > 40 else ""),
                    "action_result": result,
                }
            return {
                "status": "error",
                "ok": False,
                "detail": result.get("error", "type failed"),
                "action_result": result,
            }
        except Exception as e:
            log.error("screen_type failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_key ───────────────────────────────────────

    @tool(
        description="Press a system key: BACK, HOME, ENTER, DEL, ESC, "
                    "VOLUME_UP, VOLUME_DOWN, MENU, POWER, etc.",
        category="screen",
        call_budget=25,
    )
    def screen_key(self, key: str) -> Dict[str, Any]:
        """Press a system key event.

        Supported keys: BACK, HOME, ENTER, DEL, ESC, VOLUME_UP, VOLUME_DOWN,
                        MENU, POWER, NOTIFICATION, RECENT_APP, DPAD_UP/DOWN/LEFT/RIGHT,
                        SPACE, TAB.
        Plain integers are also accepted as raw keycodes.
        """
        if not _is_adb_available():
            return _adb_not_available_error()

        try:
            ctrl = self._get_controller()
            result = ctrl.press_key(keycode=key)

            ok = result.get("ok", result.get("status") == "ok")
            if ok:
                return {
                    "status": "success",
                    "ok": True,
                    "detail": f"pressed {key}",
                    "action_result": result,
                }
            return {
                "status": "error",
                "ok": False,
                "detail": result.get("error", f"key {key} failed"),
                "action_result": result,
            }
        except Exception as e:
            log.error("screen_key failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_act ───────────────────────────────────────

    @tool(
        description="High-level 'do X' command: automatically resolves the "
                    "target element and executes the appropriate action. "
                    "Examples: 'tap Confirm', 'swipe up', 'type hello world', "
                    "'press back'.",
        category="screen",
        call_budget=25,
    )
    def screen_act(self, instruction: str) -> Dict[str, Any]:
        """Execute a natural language screen instruction.

        The AI just says what it wants (e.g. "tap the login button"),
        and this tool figures out the action type + target automatically.

        Supported instruction patterns:
        - "tap <label>" → tap an element by its label
        - "click <label>" → same as "tap"
        - "swipe up" / "scroll down" → swipe direction
        - "type <text>" → type text into focused field
        - "press back" / "press home" → system key
        """
        if not _is_adb_available():
            return _adb_not_available_error()

        try:
            ctrl = self._get_controller()
            il = instruction.lower().strip()

            # Parse instruction into (action, param)
            action, param = self._parse_instruction(il)
            result = ctrl.act_and_verify(action=action, param=param, verify=True)

            ok = result.get("ok", result.get("status") == "success")
            if ok:
                return {
                    "status": "success",
                    "ok": True,
                    "detail": result.get("detail", f"acted on '{instruction}'"),
                    "action": action,
                    "param": param,
                    "verified": result.get("verified", True),
                    "action_result": result,
                }
            return {
                "status": "error",
                "ok": False,
                "detail": result.get("error", f"action '{instruction}' failed"),
                "action": action,
                "param": param,
                "action_result": result,
            }
        except Exception as e:
            log.error("screen_act failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Tool: screen_state ─────────────────────────────────────

    @tool(
        description="Get the current screen state: all elements, description, "
                    "and available capture sources.",
        category="screen",
        call_budget=25,
    )
    def screen_state(self) -> Dict[str, Any]:
        """Return the current full screen state as a structured dict.

        Includes: screenshot path, description, element list, element counts,
        and available capture backends. Works on MOCK when ADB is unavailable.
        """
        try:
            ctrl = self._get_controller()
            return ctrl.state_snapshot()
        except Exception as e:
            log.error("screen_state failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Internal: element formatting ──────────────────────────

    @staticmethod
    def _format_element(element: Dict, match_type: str) -> Dict[str, Any]:
        """Format an element dict for AI-friendly response output."""
        b = element.get("bounds", {})
        return {
            "label": element.get("label", "") or element.get("text", ""),
            "class": element.get("class", ""),
            "match_type": match_type,
            "match_score": element.get("_match_score", 0),
            "clickable": element.get("clickable", False),
            "coords": {
                "center_x": b.get("center_x", 0) if b else 0,
                "center_y": b.get("center_y", 0) if b else 0,
                "left": b.get("left", 0) if b else 0,
                "top": b.get("top", 0) if b else 0,
                "right": b.get("right", 0) if b else 0,
                "bottom": b.get("bottom", 0) if b else 0,
            },
            "resource_id": element.get("res_id", ""),
        }

    # ── Internal: instruction parser ───────────────────────────

    @staticmethod
    def _parse_instruction(il: str):
        """Parse a natural language instruction into (action, param)."""
        # Tap / click / press
        for kw in ("tap", "click", "press"):
            if il.startswith(kw + " "):
                param = il[len(kw) + 1:].strip()
                # Remove common filler words
                for filler in ("the ", "a ", "on ", "button ", "icon "):
                    param = param.replace(filler, "")
                if param:
                    return "tap", param
                return "tap", ""

        # Swipe / scroll
        if il.startswith("swipe ") or il.startswith("scroll "):
            parts = il.split()
            direction = parts[1] if len(parts) > 1 else "up"
            valid_dirs = ("up", "down", "left", "right")
            if direction in valid_dirs:
                return f"swipe_{direction}", ""
            return "swipe_up", ""

        # Type / enter / input
        for sep in ("type ", "enter ", "input "):
            if il.startswith(sep):
                text = il[len(sep):].strip()
                return "type", text

        # Back / home
        if "back" in il:
            return "back", ""
        if "home" in il:
            return "home", ""

        # Default: treat whole thing as a tap target
        return "tap", il.strip()

    def __repr__(self) -> str:
        return (
            f"ScreenWorker("
            f"worker_id={self.worker_id}, "
            f"tools={sorted(self.tools.keys())}, "
            f"ctrl={'loaded' if self._ctrl else 'lazy'})"
        )


__all__ = ["ScreenWorker"]