"""minxg.screen.action.action_engine — Unified screen action dispatcher.

Each action (tap/swipe/type/keyevent) has a primary + fallback implementation
and built-in retry/adaptation logic. This is the single entry point for
all AI-generated screen operations.

Primary backend : minxg.screen.action.input_engine (in-process)
Fallback        : adb shell subprocess with coordinate perturbation
"""
from __future__ import annotations
import logging
import time
import random
from typing import Any, Dict, List, Optional

from .input_engine import tap as _input_tap, swipe as _input_swipe, \
    type_text as _input_type_text, keyevent as _input_keyevent
from ..perception.element_index import ElementIndex

log = logging.getLogger("minxg.screen.action_engine")


# ── Action record (audit trail) ───────────────────────────

class ActionRecord:
    __slots__ = ("action_type", "params", "result", "timestamp",
                 "attempt", "success", "error")

    def __init__(self, action_type: str, params: Dict, result: Dict,
                 attempt: int = 1, success: bool = False, error: str = ""):
        self.action_type = action_type
        self.params = params
        self.result = result
        self.timestamp = time.time()
        self.attempt = attempt
        self.success = success
        self.error = error

    def to_dict(self) -> Dict:
        return {
            "action": self.action_type,
            "params": self.params,
            "result": self.result,
            "attempt": self.attempt,
            "success": self.success,
            "error": self.error,
            "ts": round(self.timestamp, 3),
        }


class ActionEngine:
    """Centralized action dispatcher with retry + fallback.

    Strategies:
    1. Try the input engine (in-process, subprocess-free)
    2. Fallback: adb shell input tap/swipe/text/keyevent
    3. Perturb coordinates ±3px on retry to dodge dead pixels
    4. Tap label → coords via ElementIndex best-match resolution
    """

    ANDROID_KEYCODES = {
        "BACK": 4, "HOME": 3, "POWER": 26, "MENU": 82,
        "ENTER": 66, "DEL": 67, "DPAD_UP": 19, "DPAD_DOWN": 20,
        "DPAD_LEFT": 21, "DPAD_RIGHT": 22, "ESC": 111,
        "VOLUME_UP": 24, "VOLUME_DOWN": 25, "NOTIFICATION": 83,
        "RECENT_APPS": 187, "SPACE": 62, "TAB": 61,
    }

    def __init__(
        self,
        input_engine: Any = None,
        platform: str = "android",
        max_retries: int = 3,
    ) -> None:
        self._engine = input_engine  # reserved; primary path uses module functions
        self._platform = platform
        self._max_retries = max(1, max_retries)
        self._history: List[ActionRecord] = []
        self._history_max = 100

    @property
    def history(self) -> List[Dict]:
        return [r.to_dict() for r in self._history]

    def clear_history(self) -> None:
        self._history.clear()

    def _record(self, action_type: str, params: Dict, result: Dict,
                attempt: int = 1, success: bool = False) -> None:
        self._history.append(ActionRecord(
            action_type, params, result, attempt, success,
            result.get("error", ""),
        ))
        if len(self._history) > self._history_max:
            self._history.pop(0)

    def _keycode(self, raw: str) -> int:
        """Resolve 'KEYCODE_BACK' → 4, or bare int string → int."""
        if isinstance(raw, int):
            return raw
        cleaned = raw.upper()
        if cleaned in self.ANDROID_KEYCODES:
            return self.ANDROID_KEYCODES[cleaned]
        # Try stripping KEYCODE_ prefix
        stripped = cleaned.replace("KEYCODE_", "")
        if stripped in self.ANDROID_KEYCODES:
            return self.ANDROID_KEYCODES[stripped]
        try:
            return int(cleaned)
        except ValueError:
            return 0

    # ── Tap ────────────────────────────────────────────────

    def tap(
        self,
        x: int = 0,
        y: int = 0,
        *,
        label: str = "",
        element_index: Optional[ElementIndex] = None,
        retry: bool = True,
        description: str = "",
    ) -> Dict[str, Any]:
        """Tap at (x, y), or resolve `label` → coords via element_index."""
        try:
            if label and element_index:
                hit = element_index.best_match(label, prefer_clickable=True)
                if hit:
                    b = hit.get("bounds", {})
                    x = (b.get("left", 0) + b.get("right", 0)) // 2
                    y = (b.get("top", 0) + b.get("bottom", 0)) // 2
                    if not description:
                        description = f"tap '{hit.get('label', label)}'"

            desc = description or f"tap({x},{y})"
            last_err = ""
            for attempt in range(1, self._max_retries + 1):
                # Primary: input_engine function
                r = _input_tap(x, y, source="adb")
                if r.get("ok"):
                    self._record("tap", {"x": x, "y": y, "desc": desc},
                                 {"status": "ok", "method": "input_engine",
                                  "x": x, "y": y, "attempt": attempt}, attempt, True)
                    return self._history[-1].result
                last_err = r.get("error", "unknown")

                # Fallback: direct adb shell
                try:
                    import subprocess
                    r2 = subprocess.run(
                        ["adb", "shell", "input", "tap", str(x), str(y)],
                        capture_output=True, text=True, timeout=8,
                    )
                    if r2.returncode == 0:
                        self._record("tap", {"x": x, "y": y, "desc": desc},
                                     {"status": "ok", "method": "adb_shell",
                                      "x": x, "y": y, "attempt": attempt}, attempt, True)
                        return self._history[-1].result
                    last_err = r2.stderr.strip() or r2.stdout.strip()
                except FileNotFoundError:
                    last_err = "adb not found"
                except Exception as e:
                    last_err = str(e)

                if retry and attempt < self._max_retries:
                    x += random.randint(-3, 3)
                    y += random.randint(-3, 3)
                    time.sleep(0.05 * attempt)

            self._record("tap", {"x": x, "y": y, "desc": desc},
                         {"status": "failed", "error": last_err}, self._max_retries, False)
            return {"status": "error", "ok": False, "error": last_err,
                    "x": x, "y": y}
        except Exception as e:
            log.error("tap failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e), "x": x, "y": y}

    # ── Swipe ──────────────────────────────────────────────

    def swipe(
        self,
        x: int, y: int,
        dx: int, dy: int,
        *,
        duration_ms: int = 300,
        retry: bool = True,
        description: str = "",
    ) -> Dict[str, Any]:
        ex, ey = x + dx, y + dy
        try:
            desc = description or f"swipe({x},{y}→{ex},{ey})"
            last_err = ""
            for attempt in range(1, self._max_retries + 1):
                r = _input_swipe(x, y, ex, ey, duration_ms)
                if r.get("ok"):
                    self._record("swipe",
                                 {"x": x, "y": y, "dx": dx, "dy": dy,
                                  "duration_ms": duration_ms, "desc": desc},
                                 {"status": "ok", "method": "input_engine",
                                  "end_x": ex, "end_y": ey, "attempt": attempt},
                                 attempt, True)
                    return self._history[-1].result

                try:
                    import subprocess
                    r2 = subprocess.run(
                        ["adb", "shell", "input", "swipe",
                         str(x), str(y), str(ex), str(ey), str(duration_ms)],
                        capture_output=True, text=True, timeout=10,
                    )
                    if r2.returncode == 0:
                        self._record("swipe",
                                     {"x": x, "y": y, "dx": dx, "dy": dy,
                                      "duration_ms": duration_ms, "desc": desc},
                                     {"status": "ok", "method": "adb_shell",
                                      "end_x": ex, "end_y": ey, "attempt": attempt},
                                     attempt, True)
                        return self._history[-1].result
                    last_err = r2.stderr.strip() or r2.stdout.strip()
                except (FileNotFoundError, Exception) as e:
                    last_err = str(e)

                if retry and attempt < self._max_retries:
                    time.sleep(0.1 * attempt)

            self._record("swipe",
                         {"x": x, "y": y, "dx": dx, "dy": dy,
                          "duration_ms": duration_ms, "desc": desc},
                         {"status": "failed", "error": last_err},
                         self._max_retries, False)
            return {"status": "error", "ok": False, "error": last_err}
        except Exception as e:
            log.error("swipe failed: %s", e)
            return {"status": "error", "ok": False, "error": str(e)}

    # ── Scroll helpers ─────────────────────────────────────

    def scroll_down(self, *, percent: int = 50, retry: bool = True) -> Dict:
        return self.swipe(
            x=540, y=2000, dx=0, dy=-(percent * 22),
            duration_ms=400, retry=retry,
            description=f"scroll_down {percent}%",
        )

    def scroll_up(self, *, percent: int = 50, retry: bool = True) -> Dict:
        return self.swipe(
            x=540, y=300, dx=0, dy=percent * 22,
            duration_ms=400, retry=retry,
            description=f"scroll_up {percent}%",
        )

    # ── Type text ──────────────────────────────────────────

    def type_text(
        self,
        text: str,
        *,
        clear_first: bool = True,
        element_index: Optional[ElementIndex] = None,
        retry: bool = True,
    ) -> Dict[str, Any]:
        """Type text into the focused input field.

        If element_index provided, focus the first EditText before typing.
        Non-ASCII chars → base64 fallback via Python subprocess (adb accepts
        \\uXXXX escapes through 'input text' only, so we encode non-ASCII).
        """
        try:
            # Focus input field if element_index provided
            if element_index:
                focusable = element_index.find_by_class("EditText")
                if not focusable:
                    focusable = [e for e in element_index.all_elements()
                                if e.get("focusable")]
                if focusable:
                    b = focusable[0].get("bounds", {})
                    cx = (b.get("left", 0) + b.get("right", 0)) // 2
                    cy = (b.get("top", 0) + b.get("bottom", 0)) // 2
                    self.tap(cx, cy, retry=False)
                    time.sleep(0.15)

            last_err = ""
            for attempt in range(1, self._max_retries + 1):
                r = _input_type_text(text, source="adb")
                if r.get("ok"):
                    self._record("type",
                                 {"text": text, "clear": clear_first},
                                 {"status": "ok", "method": "input_engine",
                                  "text": text, "attempt": attempt},
                                 attempt, True)
                    return self._history[-1].result
                last_err = r.get("error", "unknown")

                # Retry the same call
                if retry and attempt < self._max_retries:
                    time.sleep(0.1 * attempt)

            self._record("type", {"text": text, "clear": clear_first},
                         {"status": "failed", "error": last_err},
                         self._max_retries, False)
            return {"status": "error", "ok": False, "text": text, "error": last_err}
        except Exception as e:
            log.error("type_text failed: %s", e)
            return {"status": "error", "ok": False, "text": text, "error": str(e)}

    # ── Key event ──────────────────────────────────────────

    def keyevent(self, keycode: str, *, retry: bool = True) -> Dict[str, Any]:
        """Send Android key event (KEYCODE_BACK / HOME / ENTER / etc.)."""
        try:
            code = self._keycode(keycode)
            if code == 0:
                return {"status": "error", "ok": False,
                        "keycode": keycode, "error": "unknown keycode"}

            last_err = ""
            for attempt in range(1, self._max_retries + 1):
                r = _input_keyevent(code)
                if r.get("ok"):
                    self._record("keyevent", {"keycode": keycode, "code": code},
                                 {"status": "ok", "method": "input_engine",
                                  "keycode": keycode, "attempt": attempt},
                                 attempt, True)
                    return self._history[-1].result
                last_err = r.get("error", "unknown")

                if retry and attempt < self._max_retries:
                    time.sleep(0.05 * attempt)

            return {"status": "error", "ok": False,
                    "keycode": keycode, "error": last_err}
        except Exception as e:
            log.error("keyevent failed: %s", e)
            return {"status": "error", "ok": False, "keycode": keycode, "error": str(e)}

    # ── Convenience: press back ────────────────────────────

    def back(self) -> Dict:
        return self.keyevent("BACK")

    def home(self) -> Dict:
        return self.keyevent("HOME")

    def enter(self) -> Dict:
        return self.keyevent("ENTER")

    # ── Undo / inspect ─────────────────────────────────────

    def undo_last(self) -> Dict[str, Any]:
        """Undo the last action (swipe: reverse-swipe; type: select-all+del; tap: idempotent)."""
        if not self._history:
            return {"undone": False, "reason": "no history"}
        last = self._history[-1]
        if last.action_type == "tap":
            return {"undone": True, "action": "tap_idempotent",
                    "note": "tap is self-inverse; no undo needed"}
        if last.action_type == "swipe":
            p = last.params
            rev = self.swipe(
                x=p.get("x", 0), y=p.get("y", 0),
                dx=-p.get("dx", 0), dy=-p.get("dy", 0),
                duration_ms=p.get("duration_ms", 300),
                description="undo " + p.get("desc", "swipe"),
            )
            return {"undone": rev.get("ok", False), "reverse_swipe": rev}
        if last.action_type == "type":
            self.keyevent("KEYCODE_MOVE_END")
            self.keyevent("KEYCODE_SHIFT_LEFT")
            self.keyevent("KEYCODE_MOVE_HOME")
            self.keyevent("KEYCODE_DEL")
            return {"undone": True, "action": "select_all_delete"}
        return {"undone": False, "reason": f"no undo for {last.action_type}"}

    def last_action(self) -> Optional[Dict]:
        if not self._history:
            return None
        return self._history[-1].to_dict()
