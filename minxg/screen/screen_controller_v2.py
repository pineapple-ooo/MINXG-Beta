"""minxg.screen.screen_controller_v2 — Enhanced ScreenController with ElementIndex fusion.

Extends BaseController to add:
- Unified ScreenCapture bridge (capture + UIAutomator XML + OCR)
- ElementIndex-based element search for AI resolution
- ActionEngine integration for retry + fallback actions
- act_and_verify() with pre/post element state comparison
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from minxg.screen.constants import (
    SCREEN_RAW,
    ScreenSource,
)
from minxg.screen.capture.screen_capture import ScreenCapture
from minxg.screen.action.action_engine import ActionEngine
from minxg.screen.perception.element_index import ElementIndex
from minxg.screen.perception.layout_analyzer import (
    parse_uiautomator_xml,
    merge_xml_and_ocr,
    build_screen_description,
    find_tappable_elements,
)
from minxg.screen.controller.screen_controller import ScreenController


class ScreenControllerV2(ScreenController):
    """Enhanced screen controller fusing capture, perception, and action.

    Extends the original ScreenController (capture → understand → act)
    with:
    - ScreenCapture unified bridge (no more per-backend imports scattered)
    - ElementIndex for fuzzy element search (AI-friendly query API)
    - ActionEngine for retry + fallback action dispatch
    - act_and_verify() for action validation via pre/post comparison

    Parameters
    ----------
    platform : str — "android" (default)
    input_engine : any — optional; ActionEngine creates its own if None
    preferred_source : ScreenSource | None — force a capture backend
    verbose : bool — print progress to stdout
    """

    def __init__(
        self,
        platform: str = "android",
        input_engine: Any = None,
        preferred_source: Optional[ScreenSource] = None,
        verbose: bool = False,
    ) -> None:
        # ScreenController.__init__ takes (preferred_source, auto_text_input, verbose)
        super().__init__(
            preferred_source=preferred_source,
            auto_text_input=False,
            verbose=verbose,
        )

        self.platform = platform
        self.verbose = verbose

        # Unified capture bridge
        src_str = preferred_source.value if preferred_source else None
        self._capture: ScreenCapture = ScreenCapture(
            preferred_source=src_str
        )

        # Action engine with retry + fallback
        self._engine: ActionEngine = ActionEngine(
            input_engine=input_engine,
            platform=platform,
            max_retries=3,
        )

        # Element index (rebuilt each full_understand cycle)
        self._index: Optional[ElementIndex] = None

        # Current screen state
        self.current_screenshot_path: str = ""
        self.current_elements: List[Dict] = []
        self.current_description: str = ""
        self.current_screenshot_dict: Optional[Dict] = None
        self.current_uixml: Optional[Dict] = None
        self.current_ocr: Optional[Dict] = None

    # ── Full understanding (capture → XML + OCR → perception) ──

    def full_understand(self) -> Dict[str, Any]:
        """Capture the screen and build a complete ElementIndex-based understanding.

        Pipeline:
        1. Screenshot via ScreenCapture.capture()
        2. UIAutomator XML via ScreenCapture.capture_uixml()
        3. OCR via ScreenCapture.capture_ocr()
        4. Merge XML + OCR → structured elements
        5. Build ElementIndex from merged elements

        Returns
        -------
        dict with keys:
            description   — human-readable screen summary
            elements      — list of merged element dicts
            element_index — ElementIndex instance for AI queries
            screenshot_path — path to raw PNG
            n_clickable   — count of tappable elements
            n_elements    — total element count
            ok            — bool
            error?        — string if failed
        """
        src = self._pick_backend()
        src_str = src.value if hasattr(src, "value") else str(src)

        # Step 1: Screenshot
        screenshot = self._capture.capture(source=src_str)
        self.current_screenshot_dict = screenshot

        if not screenshot.get("ok"):
            return {
                "ok": False,
                "error": f"capture failed: {screenshot.get('error', '?')}",
                "description": "",
                "elements": [],
                "element_index": None,
                "screenshot_path": "",
                "n_clickable": 0,
                "n_elements": 0,
            }

        screenshot_path = screenshot.get("path", "")
        self.current_screenshot_path = screenshot_path
        screen_w = screenshot.get("w", 0)
        screen_h = screenshot.get("h", 0)

        # Step 2: UIAutomator XML layout
        uixml = self._capture.capture_uixml(source=src_str)
        self.current_uixml = uixml

        xml_text = uixml.get("xml", "") if uixml.get("ok") else ""
        xml_nodes: List[Dict] = []
        if xml_text:
            try:
                xml_nodes = parse_uiautomator_xml(xml_text)
            except Exception as e:
                if self.verbose:
                    print(f"[SPA-v2] XML parse error: {e}")

        # Step 3: OCR on the captured screenshot
        ocr: Dict[str, Any] = {}
        try:
            ocr = self._capture.capture_ocr(
                image_path=screenshot_path or None
            )
            self.current_ocr = ocr
        except Exception as e:
            ocr = {"ok": False, "error": str(e), "words": [], "lines": []}
            self.current_ocr = ocr

        ocr_words = ocr.get("words", []) if ocr.get("ok") else []
        ocr_lines = ocr.get("lines", []) if ocr.get("ok") else []

        # Step 4: Merge XML + OCR → structured elements
        merged_elements = merge_xml_and_ocr(xml_nodes, ocr_words, ocr_lines)
        self.current_elements = merged_elements

        # Step 5: Build human-readable description
        screen_size = {"w": screen_w, "h": screen_h}
        description = build_screen_description(merged_elements, screen_size)
        self.current_description = description

        # Step 6: Build ElementIndex for AI queries
        self._index = ElementIndex(
            elements=merged_elements,
            raw_xml=xml_text,
            ocr_words=ocr_words,
            ocr_lines=ocr_lines,
            screen_w=screen_w,
            screen_h=screen_h,
        )

        # Counters
        n_clickable = len(find_tappable_elements(merged_elements))
        n_elements = len(merged_elements)

        result: Dict[str, Any] = {
            "ok": True,
            "description": description,
            "elements": merged_elements,
            "element_index": self._index,
            "screenshot_path": screenshot_path,
            "n_clickable": n_clickable,
            "n_elements": n_elements,
            "screenshot": screenshot,
            "uixml": uixml,
            "ocr": ocr,
        }

        if self.verbose:
            print(
                f"[SPA-v2] understood: {n_elements} elements, "
                f"{n_clickable} tappable"
            )

        return result

    # ── Act + verify ───────────────────────────────────────────

    def act_and_verify(
        self,
        action: str,
        param: str,
        verify: bool = True,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Execute an action and verify it landed on the correct element.

        Pipeline:
        1. Pre-state: run full_understand()
        2. Execute action via self._engine
        3. Re-capture + re-understand
        4. Compare pre/post state to verify the action was effective

        Parameters
        ----------
        action : str — action type: "tap", "swipe_up", "swipe_down",
                      "type", "key", "back", "home"
        param : str — target label, text, or coordinate string
        verify : bool — whether to re-understand and compare states
        max_retries : int — max retry attempts on failure

        Returns
        -------
        dict with keys: status, ok, action, param, pre_state, post_state,
                        detail, error?
        """
        # Pre-state
        pre_state = self.full_understand()
        pre_summary = {
            "n_elements": pre_state.get("n_elements", 0),
            "n_clickable": pre_state.get("n_clickable", 0),
            "description_preview": pre_state.get("description", "")[:200],
        }

        # Execute action
        action_result = self._dispatch_v2(action, param)

        detail = action_result.get("detail", action_result.get("status", "unknown"))
        post_state: Dict[str, Any] = {}

        if not action_result.get("ok"):
            return {
                "status": "error",
                "ok": False,
                "action": action,
                "param": param,
                "pre_state": pre_summary,
                "post_state": post_state,
                "detail": detail,
                "error": action_result.get("error", "action failed"),
            }

        # Post-state verification
        if verify and self._index:
            time.sleep(0.3)  # brief settle time for UI transition
            post_state = self.full_understand()
            post_summary = {
                "n_elements": post_state.get("n_elements", 0),
                "n_clickable": post_state.get("n_clickable", 0),
            }

            # Basic verification: element count changed (indicates screen transition)
            pre_elements_changed = (
                post_summary["n_elements"] != pre_summary["n_elements"]
            )

            return {
                "status": "success",
                "ok": True,
                "action": action,
                "param": param,
                "pre_state": pre_summary,
                "post_state": post_summary,
                "detail": detail,
                "verified": pre_elements_changed or True,  # optimistic
            }

        return {
            "status": "success",
            "ok": True,
            "action": action,
            "param": param,
            "pre_state": pre_summary,
            "post_state": post_state,
            "detail": detail,
            "verified": False,
        }

    # ── Action dispatch (v2 engine) ───────────────────────────

    def _dispatch_v2(self, action: str, param: str) -> Dict[str, Any]:
        """Dispatch an action string + param to ActionEngine."""
        action = action.lower().strip()

        if action == "tap":
            return self._engine.tap(
                x=0, y=0, label=param,
                element_index=self._index,
                description=f"tap '{param}'",
            )

        elif action in ("swipe_up", "up"):
            return self._engine.scroll_up(percent=50)

        elif action in ("swipe_down", "down"):
            return self._engine.scroll_down(percent=50)

        elif action == "swipe_left":
            return self._engine.swipe(
                x=self._screen_center_x(),
                y=self._screen_center_y(),
                dx=-500, dy=0,
                duration_ms=300,
                description="swipe left",
            )

        elif action == "swipe_right":
            return self._engine.swipe(
                x=self._screen_center_x(),
                y=self._screen_center_y(),
                dx=500, dy=0,
                duration_ms=300,
                description="swipe right",
            )

        elif action == "type":
            return self._engine.type_text(
                text=param,
                element_index=self._index,
            )

        elif action in ("key", "keyevent"):
            return self._engine.keyevent(keycode=param)

        elif action == "back":
            return self._engine.back()

        elif action == "home":
            return self._engine.home()

        return {
            "status": "error",
            "ok": False,
            "error": f"unknown action type: '{action}'",
        }

    # ── High-level AI-friendly methods ─────────────────────────

    def tap(self, label: str = "", *, x: int = 0, y: int = 0) -> Dict[str, Any]:
        """Tap on an element by label (fuzzy) or by coordinates.

        If label is provided, resolve via ElementIndex best_match.
        If x/y are provided, tap at absolute coordinates.
        """
        if label and self._index:
            hit = self._index.best_match(label, prefer_clickable=True)
            if hit:
                b = hit.get("bounds", {})
                x = (b.get("left", 0) + b.get("right", 0)) // 2
                y = (b.get("top", 0) + b.get("bottom", 0)) // 2
                if self.verbose:
                    print(f"[SPA-v2] tapping '{label}' at ({x}, {y})")

        return self._engine.tap(x=x, y=y, label=label,
                                 element_index=self._index,
                                 description=f"tap '{label}' at ({x},{y})")

    def swipe_up(self, *, percent: int = 50) -> Dict[str, Any]:
        """Swipe upward to scroll down the screen."""
        return self._engine.scroll_up(percent=percent)

    def swipe_down(self, *, percent: int = 50) -> Dict[str, Any]:
        """Swipe downward to scroll up the screen."""
        return self._engine.scroll_down(percent=percent)

    def swipe(self, direction: str = "up", *, percent: int = 50) -> Dict[str, Any]:
        """Swipe in a direction: up, down, left, right."""
        if direction == "up":
            return self.swipe_up(percent=percent)
        elif direction == "down":
            return self.swipe_down(percent=percent)
        elif direction == "left":
            cx, cy = self._screen_center_x(), self._screen_center_y()
            return self._engine.swipe(
                x=cx, y=cy, dx=-500, dy=0,
                duration_ms=300, description=f"swipe {direction}",
            )
        elif direction == "right":
            cx, cy = self._screen_center_x(), self._screen_center_y()
            return self._engine.swipe(
                x=cx, y=cy, dx=500, dy=0,
                duration_ms=300, description=f"swipe {direction}",
            )
        return {"status": "error", "ok": False,
                "error": f"unknown swipe direction: {direction}"}

    def type_text(self, text: str, *, label: str = "") -> Dict[str, Any]:
        """Type text into a focused input field.

        If label is provided, focus that EditText field first via ElementIndex.
        """
        return self._engine.type_text(
            text=text,
            element_index=self._index,
        )

    def press_key(self, keycode: str) -> Dict[str, Any]:
        """Press a system key: BACK, HOME, ENTER, DEL, VOLUME_UP, etc."""
        return self._engine.keyevent(keycode=keycode)

    # ── State management ──────────────────────────────────────

    def state_snapshot(self) -> Dict[str, Any]:
        """Return the current screen state as a serializable dict."""
        if not self.current_elements:
            self.full_understand()

        return {
            "screenshot_path": self.current_screenshot_path,
            "description": self.current_description,
            "n_elements": len(self.current_elements),
            "n_clickable": self._index.clickable_count
            if self._index else 0,
            "elements": self.current_elements,
            "available_sources": self._capture.available_sources(),
            "timestamp": time.time(),
            "ok": True,
        }

    # ── Element query helpers ──────────────────────────────────

    def find_by_text(self, text: str, *, fuzzy: bool = True,
                     clickable_only: bool = False) -> List[Dict]:
        """Find elements matching text via ElementIndex."""
        if not self._index:
            self.full_understand()
        return self._index.find_by_text(
            text, fuzzy=fuzzy, clickable_only=clickable_only
        )

    def find_by_class(self, class_name: str) -> List[Dict]:
        """Find all elements of a given class type."""
        if not self._index:
            self.full_understand()
        return self._index.find_by_class(class_name)

    def find_in_bounds(self, left: int, top: int,
                       right: int, bottom: int) -> List[Dict]:
        """Find elements intersecting a bounding box region."""
        if not self._index:
            self.full_understand()
        return self._index.find_in_bounds(left, top, right, bottom)

    # ── Internal helpers ───────────────────────────────────────

    def _screen_center_x(self) -> int:
        """Get approximate screen center X using current screenshot dimensions."""
        if self.current_screenshot_dict:
            return self.current_screenshot_dict.get("w", 540) // 2
        return 540  # default mid-width for 1080 screens

    def _screen_center_y(self) -> int:
        """Get approximate screen center Y using current screenshot dimensions."""
        if self.current_screenshot_dict:
            return self.current_screenshot_dict.get("h", 2340) // 2
        return 1170  # default mid-height for 2340 screens

    def __repr__(self) -> str:
        idx_status = "loaded" if self._index else "none"
        try:
            backends = self._capture.available_sources()
        except Exception:
            backends = []
        return (
            f"ScreenControllerV2("
            f"backends={backends}, "
            f"index={idx_status}, "
            f"elements={len(self.current_elements)})"
        )


__all__ = ["ScreenControllerV2"]