#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.ai.safety.guard — break out of LLM tool-call loops.

Background
==========
Modern agents keep calling the same tool over and over with similar
arguments. Replete loops burn tokens and never reach the user.
This guard watches every tool call and breaks the loop as soon as a
defined exhaustion criterion fires.

Three criteria, all local & exact, no LLM round-trip:

  1. depth       — max tool calls per turn (default 8)
  2. duplicate   — same (name, args_hash) repeated within K calls
  3. cost        — total token-equivalent wall-clock cost; hard ceiling

When any criterion fires, ``pre_check(...)`` returns
``(allowed=False, reason=<code>)``. The orchestrator should surface
the reason to the user verbatim; the guard does *not* silently
swallow the call.

The guard is sync; it's safe to call from a thread-pool executor.
Failure mode is conservative: if the guard raises, it returns
``(True, None)`` so the chain progresses. A disabled guard raises
nothing.
"""
from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import logging
import os
import platform
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("src.ai.safety")


# -------------------------------------------------------------------- env --
# Tunables via env vars so install / CI can override without code changes.

def _env_int(name: str, default: int) -> int:
    try:
        v = os.environ.get(name)
        return int(v) if v is not None and v.strip() else default
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        v = os.environ.get(name)
        return float(v) if v is not None and v.strip() else default
    except (TypeError, ValueError):
        return default


MAX_DEPTH_DEFAULT = _env_int("MINXG_MAX_DEPTH", 8)
DEDUP_WINDOW_DEFAULT = _env_int("MINXG_DEDUP_WINDOW", 4)
COST_CEIL_MS_DEFAULT = _env_float("MINXG_COST_CEIL_MS", 30_000.0)


# ─────────────────────────────────────────────────────────────── is_mobile --

def _is_mobile_environment() -> bool:
    """Heuristic: tiny screen, low power, or any Termux/* env hint => mobile.

    Used only to soften the depth / cost ceilings on resource-tight
    devices — never to *raise* them.
    """
    if os.environ.get("MINXG_IS_MOBILE") == "1":
        return True
    if os.environ.get("TERMUX_VERSION"):
        return True
    if os.environ.get("ZERO_TERMUX"):
        return True
    try:
        uname = platform.uname().machine or ""
        if uname.startswith(("aarch64", "armv7", "armv8l")):
            return True
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────────────────────── DepthGuard --


class DepthGuard:
    """Hard ceiling on the count of tool calls per turn.

    Reset is the orchestrator's job; ``reset()`` zeroes the counter
    when a new user turn starts.
    """

    def __init__(self, max_depth: int = MAX_DEPTH_DEFAULT) -> None:
        self.max_depth = max_depth
        self._count = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._count += 1
            return self._count

    def reset(self) -> None:
        with self._lock:
            self._count = 0

    @property
    def count(self) -> int:
        return self._count

    @property
    def remaining(self) -> int:
        return max(0, self.max_depth - self._count)


# ─────────────────────────────────────────────────────────────── DupDetector --


class DupDetector:
    """Reject repeated calls within the last `window_size` calls.

    The hash is over ``(tool_name, serialised-args)``, where args are
    canonicalised through ``json.dumps(..., sort_keys=True,
    default=str)`` so ``{"a": 1, "b": 2}`` and ``{"b": 2, "a":
    1}`` hash equal. Floating-point nan tokens are serialised via
    the default=str escape so they don't break the encoder.
    """

    def __init__(self, window_size: int = DEDUP_WINDOW_DEFAULT) -> None:
        if window_size < 1:
            window_size = 1
        self.window_size = window_size
        self._recent: Deque[str] = deque(maxlen=window_size)

    @staticmethod
    def _fingerprint(name: str, args: Dict[str, Any]) -> str:
        try:
            canonical = json.dumps(args, sort_keys=True, default=str,
                                   ensure_ascii=False)
        except (TypeError, ValueError):
            canonical = repr(sorted(args.items()))
        return hashlib.sha256(
            f"{name}|{canonical}".encode("utf-8")
        ).hexdigest()[:16]

    def check(self, name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Return ``(allowed, fp)``. ``allowed=False`` means dup."""
        fp = self._fingerprint(name, args)
        if fp in self._recent:
            return False, fp
        self._recent.append(fp)
        return True, fp

    def reset(self) -> None:
        self._recent.clear()


# ─────────────────────────────────────────────────────────────── CostGuard ---


class CostGuard:
    """Hard wall-clock ceiling per turn (~token-cost heuristic).

    This is a *local* measure: we don't have the per-call token
    breakdown here, so we approximate it with the actual time the
    tool took to run. The default 30 s ceiling is generous: a
    well-behaved minute-long session rarely exceeds that per turn.
    Override via ``MINXG_COST_CEIL_MS`` on tight CI runners.
    """

    def __init__(self, ceiling_ms: float = COST_CEIL_MS_DEFAULT) -> None:
        self.ceiling_ms = ceiling_ms
        self._total_ms = 0.0
        self._lock = threading.Lock()

    def record(self, duration_ms: float) -> None:
        if duration_ms < 0:
            duration_ms = 0.0
        with self._lock:
            self._total_ms += duration_ms

    @property
    def total_ms(self) -> float:
        return self._total_ms

    def reset(self) -> None:
        with self._lock:
            self._total_ms = 0.0


# ─────────────────────────────────────────────────────────────── AntiLoopGuard --


class AntiLoopGuard:
    """Top-level guard. Pre/post check + telemetry.

    Usage::

        guard = AntiLoopGuard()
        allowed, reason = guard.pre_check("shell", {"cmd": "ls"})
        if not allowed:
            return json.dumps({"error": reason, "blocked": True})
        t0 = time.time()
        ... # run the tool
        guard.record("shell", {"cmd": "ls"}, result, duration_ms=...)
    """

    def __init__(
        self,
        *,
        max_depth: int = MAX_DEPTH_DEFAULT,
        dedup_window: int = DEDUP_WINDOW_DEFAULT,
        cost_ceiling_ms: float = COST_CEIL_MS_DEFAULT,
        is_mobile: Optional[bool] = None,
    ) -> None:
        if is_mobile is None:
            is_mobile = _is_mobile_environment()
        # Soften ceilings on mobile: smaller windows mean tighter
        # detection without raising global limits on full builds.
        if is_mobile:
            max_depth = min(max_depth, 5)
            dedup_window = min(dedup_window, 3)
            cost_ceiling_ms = min(cost_ceiling_ms, 12_000.0)

        self.is_mobile = is_mobile
        self.depth_guard = DepthGuard(max_depth=max_depth)
        self.dup_detector = DupDetector(window_size=dedup_window)
        self.cost_guard = CostGuard(ceiling_ms=cost_ceiling_ms)
        self._stats: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    # ----- public API -----

    def pre_check(self, name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Return ``(allowed, reason_or_none)``.

        ``reason`` is a short string safe to print to a user when
        the orchestrator surfaces the block.

        Reasons:
          * ``"depth_exceeded"``
          * ``"duplicate"``
          * ``"cached"``           — call repeated but inside
                                       window but recoverable;
                                       orchestrator can still proceed
                                       when it has the cached result
          * ``"cost_exceeded"``
        """
        try:
            n = self.depth_guard.increment()
            if n > self.depth_guard.max_depth:
                return False, "depth_exceeded"

            args_dict = args if isinstance(args, dict) else {"_": args}
            allowed, fp = self.dup_detector.check(name, args_dict)
            if not allowed:
                # Treat as a cached-result opportunity — the
                # orchestrator may already have the answer and
                # proceed; we just don't re-run the tool.
                return False, "cached"

            if self.cost_guard.total_ms > self.cost_guard.ceiling_ms:
                return False, "cost_exceeded"

            return True, None
        except Exception as e:  # pragma: no cover — defence in depth
            logger.warning("AntiLoopGuard.pre_check raised: %r", e)
            return True, None

    def record(
        self,
        name: str,
        args: Dict[str, Any],
        result: Any,
        *,
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> None:
        """Bookkeeping after a tool finishes. Never raises."""
        try:
            self.cost_guard.record(float(duration_ms))
            with self._lock:
                self._stats.append({
                    "name": name,
                    "args": args if isinstance(args, dict) else {"_": args},
                    "success": bool(success),
                    "duration_ms": float(duration_ms),
                    "ts": time.time(),
                })
                # cap the in-memory trail so noisy sessions don't
                # balloon the guard's footprint
                if len(self._stats) > 1024:
                    self._stats = self._stats[-512:]
        except Exception as e:  # pragma: no cover
            logger.debug("AntiLoopGuard.record ignored: %r", e)

    def reset(self) -> None:
        """Reset all counters. Call at the start of each user turn."""
        self.depth_guard.reset()
        self.dup_detector.reset()
        self.cost_guard.reset()

    def get_context_injection(self) -> str:
        """One-shot TRAJECTORY hint that prompts the LLM to break out of a loop.

        Returns an empty string when the guard has no evidence of
        a tool-call loop; otherwise returns a short instruction
        that the caller can spray into the next prompt so the model
        notices that, say, ``3 duplicate calls in the last 4
        attempts`` is suspicious.
        """
        try:
            depth = self.depth_guard.count
            cap = self.depth_guard.max_depth
            near = depth >= max(1, cap - 2)
            with self._lock:
                # count duplicates in the recent trail
                recent_names: Dict[str, int] = {}
                for ev in self._stats:
                    n = ev.get("name", "")
                    recent_names[n] = recent_names.get(n, 0) + 1
            dup = max(recent_names.values()) if recent_names else 0
            flags: List[str] = []
            if near:
                flags.append(f"deep into tool-call budget ({depth}/{cap})")
            if dup >= 3:
                flags.append(f"repeated the same tool {dup}× in this turn")
            if not flags:
                return ""
            return ("[anti-loop] " + "; ".join(flags)
                    + ". Stop calling tools and answer the user.")
        except Exception:
            return ""

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "depth": self.depth_guard.count,
                "depth_max": self.depth_guard.max_depth,
                "recent": list(self._stats),
                "cost_ms": self.cost_guard.total_ms,
                "cost_max_ms": self.cost_guard.ceiling_ms,
                "is_mobile": self.is_mobile,
            }


# ────────────────────────────────────────────────────────── singleton -----


_GUARDS: Dict[str, AntiLoopGuard] = {}
_GUARDS_LOCK = threading.Lock()


def get_guard(*, is_mobile: Optional[bool] = None) -> AntiLoopGuard:
    """Process-wide singleton, lazily built on first call."""
    key = "mobile" if is_mobile else "default"
    with _GUARDS_LOCK:
        g = _GUARDS.get(key)
        if g is None:
            g = AntiLoopGuard(is_mobile=is_mobile)
            _GUARDS[key] = g
        return g


def reset_guard(*, is_mobile: Optional[bool] = None) -> None:
    """Reset the singleton — useful between tests."""
    key = "mobile" if is_mobile else "default"
    with _GUARDS_LOCK:
        g = _GUARDS.get(key)
        if g is not None:
            g.reset()


# ----------------------------------------------------------------- cli ----


def _self_check() -> int:  # pragma: no cover — used by build/doctor scripts
    """Cheap integration smoke. Returns 0 on success, 1 on regression."""
    g = AntiLoopGuard(max_depth=3, dedup_window=2, cost_ceiling_ms=50.0)

    a1, r1 = g.pre_check("shell", {"cmd": "ls"})
    assert a1 and r1 is None, f"first call should pass, got {(a1, r1)}"

    a2, r2 = g.pre_check("shell", {"cmd": "ls"})
    assert not a2 and r2 in ("cached", "duplicate"), \
        f"dup should be blocked, got {(a2, r2)}"

    g2 = AntiLoopGuard(max_depth=2, dedup_window=4, cost_ceiling_ms=10.0)
    g2.pre_check("a", {})
    g2.pre_check("b", {})
    a3, r3 = g2.pre_check("c", {})
    assert not a3 and r3 == "depth_exceeded", \
        f"third call over depth=2 should fire, got {(a3, r3)}"

    g3 = AntiLoopGuard(max_depth=5, dedup_window=4, cost_ceiling_ms=20.0)
    g3.record("x", {}, None, duration_ms=15.0)
    a4, r4 = g3.pre_check("y", {})
    assert not a4 and r4 == "cost_exceeded", \
        f"single 15ms call should bust the 20ms ceiling, got {(a4, r4)}"
    return 0


# Allow `python -m src.ai.safety.guard` smoke runs.
if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_self_check())
