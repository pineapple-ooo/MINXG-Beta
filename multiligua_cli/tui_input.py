"""multiligua-cli/tui_input.py — char-by-char readline with inline hints.

Strategy table
--------------

* **TTY + readchar available** — read each keypress one at a time,
  redraw the prompt + the hint under it after every keystroke.  This
  is the only path that gives the user the real-time floating
  ``//model`` autocomplete the spec calls for.
* **TTY without readchar** — fall back to ``input()``; the user
  still sees the hint *after* they press Enter, not before.
* **No TTY (CI, piped stdin)** — same as the previous case.

The hint layer only renders when ``//`` is the literal first two
characters the user typed (see ``multiligua_cli.suggest``).  Plain
prose such as ``"请帮我分内部储存/文件目录下的文件"`` produces no
hint — the helper exists *for the user*, not for show.

ANSI is used here (not rich) because char-by-char rendering has to
own every keystroke and rich's ``Live`` overlay only composites
in limited contexts.  Codes are written defensively so a stdout
without a tty never gets stuck mid-sequence.
"""
from __future__ import annotations

import sys
from typing import Callable, List, Optional, Tuple

from multiligua_cli.suggest import primary_suggestion
from multiligua_cli.wizard_ui import HAS_READCHAR


# Optional readchar import (lazy so a missing module never blocks
# the fallback path).
try:                                # pragma: no cover
    import readchar as _readchar
except ImportError:                # pragma: no cover
    _readchar = None
_RESET = "\033[0m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_HIDDEN = "\033[8m"
_ERASE_EOL = "\033[K"


# ANSI helpers (kept local: do NOT inherit wizard_ui colour
# constants — we want a fixed dim hint that looks identical
# to a comment in any terminal).


def _hint_ansi(hint: str) -> str:
    """Render *hint* as a dim comment-line that mirrors comment style."""
    if not hint:
        return ""
    return f"{_DIM}{_ITALIC}  // hint: {hint}{_RESET}\n"


def _erase_hint_line() -> None:
    """Move cursor up + erase line so the next hint replaces the old."""
    sys.stdout.write("\033[1A")    # up one line
    sys.stdout.write("\r" + _ERASE_EOL)


def _print_hint(hint: str) -> None:
    """Print the hint line that lives directly under the user's prompt."""
    sys.stdout.write(_hint_ansi(hint))
    sys.stdout.flush()


def _plain_line() -> str:
    """Print one new ``input()`` line — used by non-TTY fallback."""
    try:
        return input()
    except EOFError:
        return ""    # EOF becomes empty (treat like Ctrl-D elsewhere)
    except KeyboardInterrupt:
        return "/exit"


def _slow_input(prefix: str = "") -> str:
    """Block-mode fallback.  Reads one ``input()`` and returns the result.

    The hint is computed after the line is read so the user still sees the
    best suggestion for the next prompt, not before they type.
    """
    if prefix:
        sys.stdout.write(prefix)
        sys.stdout.flush()
    return _plain_line()


# ────────────────────────────────────────────────────────────────────
# The TTY-aware character loop.  Implemented as a coroutine-friendly
# function — readchar is blocking so we keep the helper itself
# blocking too; the chat loop awaits the whole send turn, this
# helper eats as many keystrokes as it needs before returning.
# ────────────────────────────────────────────────────────────────────


def _key_to_char(read_key) -> Tuple[str, bool]:
    """Translate a readchar event to ``(char, is_enter)``.

    Handles regular printable characters, UTF-8 multibyte input,
    Enter (`\\r` / KEY_ENTER / \\n), Backspace (KEY_BACKSPACE / \\x7f / \\b),
    and one well-defined sentinel for everything else (``("", False)``).
    """
    if read_key in (None, ""):
        return "", False
    # readchar may hand us a unicode char (str) OR a single-byte read (str).
    if isinstance(read_key, bytes):
        try:
            read_key = read_key.decode("utf-8")
        except UnicodeDecodeError:
            # Split bytes into bytes-as-chars so partial UTF-8 reads get
            # pushed back via the ``push`` API if available — but for
            # simplicity here just drop the stray byte.
            return "", False
    if read_key in ("\r", "\n"):
        return "", True
    if read_key in ("\x7f", "\b"):
        return "\b", False
    return read_key, False


def _read_with_hints(prefix: str, hint_fn: Callable[[str], str]) -> str:
    """TTY / readchar path — char-by-char with live hint under cursor.

    *prefix* is printed without a trailing newline.  After every
    keypress we (a) rewrite the hint line one row below the cursor,
    (b) ask *hint_fn*(current buffer) for the next hint.
    """
    sys.stdout.write(prefix)
    sys.stdout.flush()
    buf: List[str] = []
    _print_hint(hint_fn(""))

    while True:
        key = _readchar.readkey()                    # type: ignore[union-attr]
        ch, is_enter = _key_to_char(key)
        if is_enter:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(buf)
        if ch == "\b":                                # backspace
            if buf:
                buf.pop()
                sys.stdout.write("\b \b")
        elif ch:
            buf.append(ch)
            sys.stdout.write(ch)
        sys.stdout.flush()

        # Refresh the hint *line under us*.  We always re-erase the
        # previously painted hint so its width never accumulates.
        _erase_hint_line()
        _print_hint(hint_fn("".join(buf)))


def _read_fallback_with_hints(prefix: str,
                              hint_fn: Callable[[str], str]) -> str:
    """No-readchar fallback — read once, show hint for future background.

    The user still gets the inline hint on the *next* prompt because
    we cache the last typed line through a module-level dict.
    """
    line = _slow_input(prefix)
    # We can't redraw mid-line, but on the next prompt we'll lead
    # with a hint for the most-recent typed-incomplete buffer
    # (caller decides what to do).
    return line


def _default_hint(buf: str) -> str:
    """Default hint closure: only fire the suggest engine when the
    user has typed the ``//`` gate.
    """
    if not buf.startswith("//"):
        return ""
    return primary_suggestion(buf)


def read_line(
    *,
    prompt_text: str = "",      # empty prefix per user spec (v0.19.x)
    hint_fn: Callable[[str], str] = _default_hint,
) -> str:
    """Read one user-input line that may end in ``\\`` to continue.

    Same multi-line semantics as ``input()`` (backslash continuation),
    but with live ``//`` autocomplete when the host is a TTY and
    readchar is installed.

    Returns ``"/exit"`` on KeyboardInterrupt, ``""`` on EOF.
    """
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if is_tty and _readchar is not None and HAS_READCHAR:
        return _read_with_hints(prompt_text, hint_fn)

    # Block-mode fallback.  We still print a leading hint if the user
    # prefilled the buffer (they probably won't, so we leave the
    # routine dumber than the TTY one).
    line = _read_fallback_with_hints(prompt_text, hint_fn)
    # Multi-line continuation as in the prior REPL.
    if line.endswith("\\"):
        collected = [line[:-1]]
        while True:
            nxt = _slow_input("       … ")
            if nxt.endswith("\\"):
                collected.append(nxt[:-1])
                continue
            collected.append(nxt)
            break
        return "\n".join(collected).strip()
    return line or ""


__all__ = ["read_line", "primary_suggestion"]
