#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multiling/platform_cap — per-platform tool budget.

Different platforms have different ceilings for what they can
host without running out of memory or hitting the LLM's tool-call
limit. We hard-cap the *registered* tool surface so the LLM never
sees more than `cap_for(platform)` at any one time.

Platform cap table (cells = max tools this platform can ship):

   android :   600  (Termux / Slim runtimes, ~2 GB / 4-core budget)
   linux   :  1000  (full Linux desktop/server)
   macos   :  1000  (matches the linux tier)
   windows :  1000  (full Windows host)
   unknown :   500  (conservative fallback)

Override per-deployment via env var ``MINXG_TOOL_CAP``.

Order
=====
Tools are kept in registry insertion order: that's the order they
were ``register()``ed at module import time. The cap is applied as
a *prefix* — the first `cap_for(platform)` tools are visible, the
rest are filtered out by ``list_active_tools()`` and
``get_tool_definitions()``. Tools remain registered so extensions
that opt in later can re-add the dropped ones without losing
definitions.
"""
from __future__ import annotations

import logging
import os
import platform as _plat
import threading
from typing import Dict, FrozenSet, List, Optional

logger = logging.getLogger("multiling.platform_cap")


_PLATFORM_CAPS: Dict[str, int] = {
    "android": 600,
    "linux": 1000,
    "macos": 1000,
    "windows": 1000,
    "unknown": 500,
}


_LOCK = threading.Lock()
_ACTIVE: Optional[FrozenSet[str]] = None
_PLATFORM_KEY: Optional[str] = None


def _platform_key() -> str:
    """Map the current host to a cap key. Cached after first call."""
    global _PLATFORM_KEY
    if _PLATFORM_KEY:
        return _PLATFORM_KEY
    sysname = _plat.system().lower()
    # Android / Termux / ZeroTermux all collapse to "android".
    # Check those first because `platform.system()` already returns
    # "Linux" on Android (we set it here when TERMUX_VERSION is
    # exposed). On the same host `platform.system()` may also be
    # "Android" via pyobjc-style overrides.
    if (sysname == "android"
        or sysname.startswith("linux")
        and (os.path.isdir("/data/data/com.termux")
             or os.environ.get("TERMUX_VERSION")
             or os.environ.get("ZERO_TERMUX")
             or os.environ.get("ZEROTERMUX_VERSION"))):
        _PLATFORM_KEY = "android"
        return _PLATFORM_KEY
    if sysname.startswith("linux"):
        _PLATFORM_KEY = "linux"
        return _PLATFORM_KEY
    if sysname == "darwin":
        _PLATFORM_KEY = "macos"
        return _PLATFORM_KEY
    keys_for_win = {"windows", "msys", "cygwin", "mingw"}
    if sysname in keys_for_win or "windows" in sysname:
        _PLATFORM_KEY = "windows"
        return _PLATFORM_KEY
    _PLATFORM_KEY = "unknown"
    return _PLATFORM_KEY


def detect_platform_key() -> str:
    """Public accessor — current platform key."""
    return _platform_key()


def cap_for(platform_key: Optional[str] = None) -> int:
    """Return the cap for `platform_key`, defaulted to the current host.

    Honours ``MINXG_TOOL_CAP`` env var when set (deployment override).
    """
    env_override = os.environ.get("MINXG_TOOL_CAP")
    if env_override and env_override.strip().isdigit():
        return max(1, int(env_override.strip()))
    return _PLATFORM_CAPS.get(platform_key or _platform_key(), 500)


def platform_table() -> Dict[str, int]:
    """Read-only copy of the cap table (for docs and CLI display)."""
    return dict(_PLATFORM_CAPS)


def _build_active(allowed_names: List[str], cap: int) -> FrozenSet[str]:
    """Trim the allowed list to the first `cap` entries."""
    if cap <= 0:
        return frozenset()
    if len(allowed_names) <= cap:
        return frozenset(allowed_names)
    return frozenset(allowed_names[:cap])


def compute_active_toolset() -> FrozenSet[str]:
    """Build the active-toolset frozenset for the current platform.

    Reads the live ``tools.registry.registry`` and keeps the first
    ``cap_for(...)`` entries by insertion order. Pure function over
    the registry at call time — caching is done in
    ``active_tools()``.
    """
    _pk = _platform_key()
    cap = cap_for(_pk)
    try:
        from tools.registry import registry
        # Avoid an import cycle by lazy-importing inside.
    except Exception as e:  # pragma: no cover — registry missing
        logger.debug("registry import failed: %r", e)
        return frozenset()
    names = list(registry._tools.keys())
    return _build_active(names, cap)


def active_tools() -> FrozenSet[str]:
    """Return the cached set of tools visible on this platform.

    Recomputes when the platform key or cap changes (deterministic
    re-evaluation per call); the call site can decide whether to
    cache the result.
    """
    global _ACTIVE, _PLATFORM_KEY
    pk = _platform_key()
    with _LOCK:
        if _ACTIVE is None or _PLATFORM_KEY != pk:
            _PLATFORM_KEY = pk
            _ACTIVE = compute_active_toolset()
            logger.info(
                "platform=%s cap=%d active=%d",
                pk, cap_for(pk), len(_ACTIVE),
            )
        return _ACTIVE


def invalidate() -> None:
    """Drop the cache — useful for tests / hot-reload."""
    global _ACTIVE, _PLATFORM_KEY
    with _LOCK:
        _ACTIVE = None
        _PLATFORM_KEY = None


def is_active(name: str) -> bool:
    """Quick check whether a tool name is on the active side."""
    return name in active_tools()


def summary() -> Dict[str, object]:
    """One-line dict summary for `minxg doctor` / `minxg status`."""
    pk = _platform_key()
    cap = cap_for(pk)
    active = active_tools()
    try:
        from tools.registry import registry
        total = len(registry._tools)
    except Exception:
        total = 0
    return {
        "platform": pk,
        "cap": cap,
        "active_count": len(active),
        "registered_count": total,
        "dropped_count": max(0, total - len(active)),
    }


# ───────────────────────────────── self-check ─────────────


def _self_check() -> int:  # pragma: no cover — `python -m`
    pk = detect_platform_key()
    c = cap_for(pk)
    s = summary()
    assert c >= 1, c
    assert s["cap"] == c
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_self_check())
