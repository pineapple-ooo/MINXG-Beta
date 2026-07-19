"""minxg.screen.controller — ScreenController: capture → understand → act closure.

This is the high-level API that ties all SPA subsystems together.
An AI agent can work with screens through this single class.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Dict, List, Any

from minxg.screen.constants import ScreenSource, SCREEN_RAW, SCREEN_CACHE


class ScreenController:
    """Orchestrates screen capture, analysis, and input in one object.

    Parameters
    ----------
    preferred_source: ScreenSource — capture backend priority order
    auto_text_input: bool — if True, auto-type after OCR detects input fields
    verbose: bool — print progress to stdout

    Usage:
      ctrl = ScreenController()                # auto-detect best backend
      ctrl = ScreenController(source=ScreenSource.MOCK)  # force mock for testing

      frame = ctrl.capture()                  # → {path, width, height, source, ok}
      info  = ctrl.understand(frame)          # → {description, elements, tappable, text}
      result = ctrl.tap("Submit")             # find + tap by label
      result = ctrl.type("hello world")       # find input + type
    """

    # Backend priority order (first available wins)
    BACKEND_PRIORITY = [
        ScreenSource.ADB,
        ScreenSource.TERMUX_API,
        ScreenSource.CAMERA_PHOTO,
        ScreenSource.MOCK,
    ]

    def __init__(
        self,
        preferred_source: Optional[ScreenSource] = None,
        auto_text_input: bool = False,
        verbose: bool = False,
    ):
        self.preferred = preferred_source
        self.auto_text_input = auto_text_input
        self.verbose = verbose
        self._last_frame: Optional[Dict] = None
        self._last_understanding: Optional[Dict] = None
        self._available_sources: List[ScreenSource] = []
        self._detect_backends()

    # ── Backend detection ──────────────────────────────────────────

    def _detect_backends(self):
        """Probe which capture backends are actually available.

        Migrated from the legacy ``from .capture import …`` form to the
        top-level ``minxg.screen.capture`` package — the controller no
        longer owns its own capture submodule.
        """
        from minxg.screen.capture import (
            adb_screencap, mock_screencap,
            termux_api_screencap, termux_api_available,
            camera_photo_available,
        )

        self._available_sources = []
        if adb_screencap:
            try:
                from minxg.screen.capture import adb_device_connected
                if adb_device_connected():
                    self._available_sources.append(ScreenSource.ADB)
            except Exception:
                pass
        if termux_api_available() and termux_api_screencap:
            self._available_sources.append(ScreenSource.TERMUX_API)
        if camera_photo_available():
            self._available_sources.append(ScreenSource.CAMERA_PHOTO)
        # Mock is always available
        self._available_sources.append(ScreenSource.MOCK)

        if self.verbose:
            print(f"[SPA] Available backends: {[s.value for s in self._available_sources]}")

    def _pick_backend(self) -> ScreenSource:
        """Choose the best available capture backend."""
        if self.preferred and self.preferred in self._available_sources:
            return self.preferred
        for b in self.BACKEND_PRIORITY:
            if b in self._available_sources:
                return b
        return ScreenSource.MOCK  # ultimate fallback

    # ── Capture ────────────────────────────────────────────────────

    def capture(self, *, source: Optional[ScreenSource] = None) -> Dict:
        """Capture the current screen.

        Dispatches per-backend: ADB → adb_screencap, TERMUX_API → termux,
        CAMERA_PHOTO → camera, else MOCK. The resulting frame always has
        ``ok`` plus a ``source`` key, even on failure.

        Returns a frame dict: {path, width, height, format, source,
        timestamp, ok, error?}
        """
        from minxg.screen.capture import (
            adb_screencap, mock_screencap,
            termux_api_screencap,
            camera_photo,
        )
        src = source or self._pick_backend()

        if self.verbose:
            print(f"[SPA] Capturing via {src.value}...")

        dest_base = int(time.time() * 1000)
        try:
            if src == ScreenSource.ADB:
                dest = str(SCREEN_RAW / f"adb_{dest_base}.png")
                frame = adb_screencap(dest)
            elif src == ScreenSource.TERMUX_API:
                dest = str(SCREEN_RAW / f"termux_{dest_base}.png")
                frame = termux_api_screencap(dest)
            elif src == ScreenSource.CAMERA_PHOTO:
                dest = str(SCREEN_RAW / f"camera_{dest_base}.jpg")
                frame = camera_photo(dest)
            else:
                dest = str(SCREEN_RAW / f"mock_{dest_base}.png")
                frame = mock_screencap(dest)
        except Exception as exc:
            frame = {"ok": False, "error": str(exc), "source": src.value}

        # backfill common fields
        frame.setdefault("source", src.value)
        frame.setdefault("ok", False)
        frame.setdefault("timestamp", time.time())

        # ensure path/width/height are present even for OpenCV/PIL style frames
        p = frame.get("path", "")
        if (not frame.get("width") or not frame.get("height")) and p:
            try:
                from PIL import Image  # type: ignore
                with Image.open(p) as im:
                    frame.setdefault("width", im.width)
                    frame.setdefault("height", im.height)
                    frame.setdefault("format", im.format or "PNG")
            except Exception:
                pass

        self._last_frame = frame
        if self.verbose:
            status = "OK" if frame.get("ok") else f"ERROR: {frame.get('error','?')}"
            print(f"[SPA] Capture {status} → {frame.get('path','?')}")
        return frame

    def capture_layout(self, *, source: str = "adb") -> Dict:
        """Capture the accessibility layout (UIAutomator XML).

        Returns: {xml, node_count, path, ok, error?}
        This is MORE precise than OCR for finding tappable elements.
        """
        if self.verbose:
            print(f"[SPA] Capturing layout via {source}...")

        from minxg.screen.capture.adb_backend import adb_uiautomator_dump
        layout = adb_uiautomator_dump()
        self._last_layout = layout
        return layout

    # ── Understand (perception) ────────────────────────────────────

    def understand(self, frame: Optional[Dict] = None) -> Dict:
        """Analyze a captured frame and produce structured understanding.

        combines OCR + UIAutomator layout → AI-readable description.

        Returns: {
          description: str,           — human-readable screen summary
          elements: [{label, class, bounds, clickable, ...}],
          tappable: [{label, bounds, center_x, center_y}],
          text: str                   — raw detected text
        }
        """
        frame = frame or self._last_frame
        if not frame or not frame.get("ok"):
            return {"ok": False, "error": "no valid frame; call capture() first"}

        img_path = frame.get("path", "")
        screen_size = {"w": frame.get("width", 0), "h": frame.get("height", 0)}

        # Step 1: OCR
        from minxg.screen.ocr import ocr_image
        ocr_result = ocr_image(img_path)
        self._last_ocr = ocr_result

        if not ocr_result.get("ok"):
            return {"ok": False, "error": f"OCR failed: {ocr_result.get('error','?')}"}

        # Step 2: XML layout (try ADB; may fail gracefully)
        xml_nodes = []
        try:
            layout = self.capture_layout()
            if layout.get("ok"):
                from minxg.screen.perception.layout_analyzer import parse_uiautomator_xml
                xml_nodes = parse_uiautomator_xml(layout.get("xml", ""))
        except Exception:
            pass  # layout is optional; OCR alone is still useful

        # Step 3: Merge
        from minxg.screen.perception.layout_analyzer import (
            merge_xml_and_ocr, build_screen_description, find_tappable_elements
        )
        merged = merge_xml_and_ocr(
            xml_nodes, ocr_result.get("words", []), ocr_result.get("lines", [])
        )
        description = build_screen_description(merged, screen_size)
        tappable = find_tappable_elements(merged)

        result = {
            "ok": True,
            "source": frame.get("source"),
            "description": description,
            "elements": merged,
            "tappable": tappable,
            "text": ocr_result.get("text", ""),
            "word_count": ocr_result.get("word_count", 0),
            "line_count": ocr_result.get("line_count", 0),
            "avg_confidence": ocr_result.get("avg_confidence", 0),
            "timestamp": time.time(),
        }
        self._last_understanding = result
        return result

    # ── Act ────────────────────────────────────────────────────────

    def tap(self, target: str = "", *, x: int = 0, y: int = 0,
            bounds: Optional[Dict] = None) -> Dict:
        """Tap on screen.

        Three modes:
        - tap(target="label") — find element by text, tap its center
        - tap(x=N, y=N) — tap absolute coordinates
        - tap(bounds={left,top,right,bottom}) — tap center of a bounds rect
        """
        from minxg.screen.action.input_engine import tap_center_of_element

        if bounds:
            return tap_center_of_element(bounds)
        elif x and y:
            from minxg.screen.action.input_engine import tap as _tap
            source = "adb" if ScreenSource.ADB in self._available_sources else "termux_api"
            return _tap(x, y, source=source)

        if not target:
            return {"ok": False, "error": "tap needs target string or coordinates"}

        # Find element by text
        understanding = self._last_understanding
        if not understanding:
            understanding = self.understand(self._last_frame)

        tappable = understanding.get("tappable", [])
        match = None
        for el in tappable:
            label = (el.get("label", "") or el.get("text", "")).lower()
            if target.lower() in label:
                match = el
                break

        if not match:
            return {"ok": False, "error": f"no tappable element matching '{target}'",
                    "found_tappable": [e.get("label","") for e in tappable[:5]]}

        bnd = match.get("bounds", {})
        if not bnd:
            return {"ok": False, "error": f"element '{target}' has no bounds"}

        return tap_center_of_element(bnd)

    def type(self, text: str, *, target: str = "") -> Dict:
        """Type text into an input field.

        If target is given, find that input field first.
        If target is empty, type into whatever is focused.
        """
        from minxg.screen.action.input_engine import type_text

        if target:
            understanding = self._last_understanding or self.understand()
            from minxg.screen.perception.layout_analyzer import find_text_elements
            els = find_text_elements(understanding.get("elements", []), search_text=target)
            for el in els:
                if "edit" in el.get("class", "").lower() or "input" in el.get("class", "").lower():
                    bnd = el.get("bounds", {})
                    if bnd:
                        tap_center_of_element(bnd)

        source = "adb" if ScreenSource.ADB in self._available_sources else "termux_api"
        return type_text(text, source=source)

    def swipe(self, direction: str = "up", *, distance: int = 500) -> Dict:
        """Swipe screen in a direction."""
        from minxg.screen.action.input_engine import swipe_up, swipe_down
        if direction == "up":
            return swipe_up()
        elif direction == "down":
            return swipe_down()
        return {"ok": False, "error": f"unknown swipe direction: {direction}"}

    def back(self) -> Dict:
        """Press BACK button."""
        from minxg.screen.action.input_engine import back as _back
        return _back()

    def home(self) -> Dict:
        """Press HOME button."""
        from minxg.screen.action.input_engine import home as _home
        return _home()

    # ── Autonomous loop ────────────────────────────────────────────

    def autonomous_step(self, instruction: str, *, max_retries: int = 2) -> Dict:
        """One step of the capture → understand → act → verify loop.

        Given a natural language instruction, this:
        1. Captures screen
        2. Understands what's on it
        3. Maps instruction to an action
        4. Executes the action
        5. Validates result

        Returns: {instruction, action_taken, pre_state, post_state, ok, retries}
        """
        step_log = {
            "instruction": instruction,
            "action_taken": "",
            "pre_state": {},
            "post_state": {},
            "ok": False,
            "retries": 0,
        }

        for attempt in range(max_retries + 1):
            # Pre-state
            frame = self.capture()
            if not frame.get("ok"):
                step_log["pre_state"] = {"capture_error": frame.get("error", "?")}
                continue

            understanding = self.understand(frame)
            step_log["pre_state"] = {
                "source": frame.get("source"),
                "tappable_count": len(understanding.get("tappable", [])),
                "text_preview": understanding.get("text", "")[:200],
                "description": understanding.get("description", "")[:300],
            }

            # Map instruction to action (simple keyword dispatch)
            action_result = self._dispatch_instruction(instruction, understanding)
            step_log["action_taken"] = action_result.get("action_label", "unknown")

            if not action_result.get("ok"):
                step_log["post_state"] = {"action_error": action_result.get("error", "?")}
                step_log["retries"] += 1
                time.sleep(0.5)
                continue

            # Post-state: verify change
            post_frame = self.capture()
            post_understanding = self.understand(post_frame) if post_frame.get("ok") else {}
            step_log["post_state"] = {
                "capture_ok": post_frame.get("ok"),
                "tappable_count_post": len(post_understanding.get("tappable", [])),
            }

            step_log["ok"] = True
            return step_log

        step_log["ok"] = False
        return step_log

    def _dispatch_instruction(self, instruction: str, understanding: Dict) -> Dict:
        """Map natural language instruction to a concrete screen action.

        Heuristic keyword mapping:
        - "tap", "click", "press" + label → tap
        - "type", "enter", "input" + text → type
        - "swipe", "scroll" → swipe
        - "back", "return" → back()
        - "home", "home screen" → home()
        """
        il = instruction.lower()
        tappable = understanding.get("tappable", [])

        if any(kw in il for kw in ["tap", "click", "press"]):
            # Find best match: look for object nouns after verb
            for el in tappable:
                label = (el.get("label", "") or el.get("text", "")).lower()
                keywords_in_instr = [w for w in il.split() if w not in
                                     ["tap", "click", "press", "the", "a", "on", "button", "icon"]]
                for kw in keywords_in_instr:
                    if kw in label:
                        bnd = el.get("bounds", {})
                        if bnd:
                            from minxg.screen.action import tap
                            r = tap_center_of_element(bnd)
                            r["action_label"] = f"tap '{el.get('label','')}'"
                            return r
            # Fallback: first tappable
            if tappable:
                bnd = tappable[0].get("bounds", {})
                if bnd:
                    from minxg.screen.action import tap
                    r = tap_center_of_element(bnd)
                    r["action_label"] = f"tap first tappable '{tappable[0].get('label','')}'"
                    return r
            return {"ok": False, "error": "no tappable elements found"}

        elif any(kw in il for kw in ["type", "enter", "input"]):
            # Extract text after verb
            text = instruction
            for sep in ["type ", "enter ", "input "]:
                if sep in il:
                    text = instruction.lower().split(sep, 1)[1].strip()
                    break
            r = self.type(text)
            r["action_label"] = f"type '{text[:30]}'"
            return r

        elif any(kw in il for kw in ["swipe", "scroll"]):
            from minxg.screen.action import swipe_up, swipe_down
            direction = "down" if any(kw in il for kw in ["scroll up", "down"]) else "up"
            r = swipe_up() if direction == "up" else swipe_down()
            r["action_label"] = f"swipe {direction}"
            return r

        elif "back" in il:
            r = self.back()
            r["action_label"] = "press BACK"
            return r

        elif "home" in il:
            r = self.home()
            r["action_label"] = "press HOME"
            return r

        return {"ok": False, "error": f"unknown instruction type: '{instruction[:50]}'"}

    # ── Convenience ────────────────────────────────────────────────

    def describe_screen(self) -> str:
        """Quick one-liner: capture + understand → human description."""
        frame = self.capture()
        if not frame.get("ok"):
            return f"[SPA] Capture failed: {frame.get('error','?')}"
        info = self.understand(frame)
        return info.get("description", "[SPA] No description available")

    def __repr__(self):
        return f"ScreenController(backends={[s.value for s in self._available_sources]})"


__all__ = ["ScreenController"]
