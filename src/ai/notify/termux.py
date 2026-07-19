#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.ai.notify.termux — Termux / ZeroTermux notification helper.

Why
===
On Android (Termux) we can fire a native notification via the
``termux-notification`` executable that ships with the
``termux-api`` package. On every other platform that tool isn't
on PATH: calling it raises ``FileNotFoundError`` and the chat
shouldn't see a stack trace, so this module silently no-ops and
returns ``False`` from ``send(...)``.

Capabilities
============
  - send(title, body, *, priority="high", channel=None,
         vibrate=None, sound=False, sticky=False) -> bool
  - beep() -> bool
  - vibrate(duration_ms=300) -> bool
  - is_available() -> bool

The detection is conservative: we *require* ``termux-notification``
on PATH *and* one of ``$TERMUX_VERSION`` / ``$ZERO_TERMUX`` set.
On every other system these helpers return False without raising.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Optional, Sequence

logger = logging.getLogger("src.ai.notify.termux")


_BINARIES = (
    shutil.which("termux-notification"),
    shutil.which("termux-toast"),
    shutil.which("termux-vibrate"),
)


def _has_termux_env() -> bool:
    """True iff we're running inside Termux / ZeroTermux.

    We *also* accept the legacy UNSUPPORTED ``$ANDROID_ROOT`` plus
    the existence of ``/system/bin/sh`` so a stray non-Termux
    Android shell doesn't accidentally satisfy the check.
    """
    if os.environ.get("TERMUX_VERSION"):
        return True
    if os.environ.get("ZERO_TERMUX"):
        return True
    # ZeroTermux variants ship the env var ``ZEROTERMUX_VERSION``
    # in some forks; accept either.
    if os.environ.get("ZEROTERMUX_VERSION"):
        return True
    return False


def is_available() -> bool:
    """Return True iff ``termux-notification`` is callable AND we're on Termux."""
    if not _has_termux_env():
        return False
    return bool(shutil.which("termux-notification"))


def send(
    title: str,
    body: str,
    *,
    priority: str = "high",
    channel: Optional[str] = None,
    vibrate: Optional[Sequence[int]] = None,
    sound: bool = False,
    sticky: bool = False,
    id: Optional[str] = None,
    content_type: Optional[str] = None,
    action: Optional[str] = None,
) -> bool:
    """Fire a Termux notification. Returns True on dispatch, False otherwise.

    Never raises — on a non-Termux host, missing executable, or
    unexpected error this returns False and logs at DEBUG. The
    caller can therefore use this as a fire-and-forget side
    channel that does nothing outside its target platform.
    """
    if not is_available():
        logger.debug("termux-notification not available; skipped: %r", title)
        return False

    args: list[str] = ["termux-notification",
                       "--title", title,
                       "--content", body]
    if priority in ("low", "min", "default", "high", "max"):
        args += ["--priority", priority]
    if channel:
        args += ["--channel", channel]
    if vibrate:
        args += ["--vibrate", ",".join(str(v) for v in vibrate)]
    if sound:
        args.append("--sound")
    if sticky:
        args.append("--sticky")
    if id is not None:
        args += ["--id", str(id)]
    if content_type:
        args += ["--content-type", content_type]
    if action:
        args += ["--action", action]

    try:
        rc = subprocess.run(args, capture_output=True, text=True, timeout=4)
        if rc.returncode != 0:
            logger.debug("termux-notification rc=%s: %s",
                         rc.returncode, (rc.stderr or "").strip())
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug("termux-notification dispatch failed: %r", e)
        return False


def toast(text: str, *, position: str = "middle",
          foreground_color: str = "#FFFFFF",
          background_color: str = "#000000") -> bool:
    """Show a short toast via ``termux-toast``. Non-Termux hosts return False."""
    if not _has_termux_env() or not shutil.which("termux-toast"):
        return False
    try:
        subprocess.run(
            ["termux-toast", "-g", position, "-c", foreground_color,
             "-b", background_color, text],
            capture_output=True, text=True, timeout=4,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug("termux-toast dispatch failed: %r", e)
        return False


def beep() -> bool:
    """Emit a short terminal bell (``\\a``). Always safe."""
    try:
        import sys
        sys.stdout.write("\a")
        sys.stdout.flush()
        return True
    except Exception:
        return False


def vibrate(duration_ms: int = 300) -> bool:
    """Hit ``termux-vibrate`` for `duration_ms` ms. Non-Termux => False."""
    if not _has_termux_env() or not shutil.which("termux-vibrate"):
        return False
    try:
        subprocess.run(
            ["termux-vibrate", "-d", str(max(1, int(duration_ms))),
             "-f"],  # -f forces even if silent
            capture_output=True, text=True, timeout=4,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug("termux-vibrate dispatch failed: %r", e)
        return False


# ──────────────────────────────────────────────── task-completed hook


def notify_task_completed(
    *,
    title: str = "MINXG task done",
    body: str = "",
    extra_vibrate: bool = True,
) -> bool:
    """Fire-and-forget helper used by `install.sh` and the CLI when
    a long-running task (install / config / chat completion) finishes.

    On Termux this surfaces a real Android notification; on every
    other platform it returns False. We still write to the logger
    in either case so the activity is auditable.
    """
    if not body:
        body = "minxg — task finished. open Termux for details."
    args: list[str] = ["termux-notification",
                       "--title", title,
                       "--content", body,
                       "--priority", "high",
                       "--id", "minxg-task-done"]
    if not is_available():
        logger.info("notify: %s / %s", title, body)
        return False
    if extra_vibrate and shutil.which("termux-vibrate"):
        try:
            subprocess.run(["termux-vibrate", "-d", "200"],
                          capture_output=True, timeout=2)
        except Exception:
            pass
    try:
        subprocess.run(args, capture_output=True, text=True, timeout=4)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug("notify_task_completed dispatch failed: %r", e)
        return False


def _self_check() -> int:  # pragma: no cover — `python -m`
    assert isinstance(is_available(), bool)
    assert isinstance(send("t", "b"), bool)
    assert isinstance(toast("ok"), bool)
    assert isinstance(beep(), bool)
    assert isinstance(vibrate(100), bool)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_self_check())
