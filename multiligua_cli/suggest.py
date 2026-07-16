"""multiligua_cli/suggest.py — slash-command autocomplete engine.

Pure functional engine — no I/O, no ansi codes, no terminal glue.
Used by the chat REPL to compute, after each keystroke, the
list of candidate completions the user might mean.  Two rules
make this engine tiny but useful:

* **Slashed-gate.**  A non-``//``-prefixed line never produces
  suggestions — ``mo`` in ``请帮我分内部储存/文件目录下的文件`` is
  ordinary prose, NOT a command attempt, so the helper returns
  ``[]`` and the input layer shows no hint line.
* **Prefix-anchored.**  Completions match against the literal
  substring the user typed after the two slashes.  ``//mo``
  matches ``//model`` and ``//mobile``, but NOT ``//memory``
  (the user's first two letters don't match).  ``//bo``
  filters to ``//boss`` / ``//both`` / … but explicitly NOT
  ``//model``.

This file is intentionally framework-free so tests can import
it without pulling the rest of the CLI stack.
"""
from __future__ import annotations

from typing import Iterable, List, Tuple, Sequence


# Ordered set of every slash command exposed in the chat REPL.
# Keep authoritative parity with the ``/help`` body in tui_chat.py
# — update both ends together when commands are added or removed.
DEFAULT_COMMANDS: Sequence[str] = (
    "/help",      "/tools",     "/status",      "/config",
    "/memory",    "/doctor",    "/setup",       "/provider",
    "/model",     "/url",       "/apikey",      "/lang",
    "/history",   "/clear",     "/forget",      "/reset",
    "/log",       "/exit",      "/quit",
    # External / vendor hooks keep their own '/' prefix but get
    # an extra shadow here so the suggest tree feels complete.
    "/boss",      "/both",      "/mobile",      "/mode",
)


def is_slash_prefix(text: str) -> bool:
    """True iff *text* starts with ``//``.

    Anything without the leading double-slash is prose, NOT a
    command, so the input layer must show no autocomplete hint.
    """
    return isinstance(text, str) and text.startswith("//")


def suggest(
    text: str,
    commands: Iterable[str] = DEFAULT_COMMANDS,
) -> Tuple[str, ...]:
    """Return ``commands`` whose body matches the substring typed
    after the leading ``//``.

    Examples
    --------
    >>> suggest("//mo", ())
    ()
    >>> suggest("//mo", ("/model", "/memory", "/mode"))
    ('/model', '/mode')                 # prefix-anchored

    >>> suggest("请帮我分内部储存/文件目录下的文件")
    ()                                  # not a slash command

    >>> suggest("//bo", ("/model", "/boss", "/both", "/memory"))
    ('/boss', '/both')                  # ``bo`` ≠ ``mo``
    """
    if not is_slash_prefix(text):
        return ()
    typed = text[len("//"):]            # the part after ``//``
    if not typed:
        # Empty body — show every command so the user picks one.
        return tuple(commands)
    out: List[str] = []
    for c in commands:
        # Strip leading slash so we compare the typed body
        # against the command body.
        body = c.lstrip("/")
        if body.startswith(typed):
            out.append(c)
    return tuple(out)


def primary_suggestion(
    text: str,
    commands: Iterable[str] = DEFAULT_COMMANDS,
) -> str:
    """Return the *first* suggestion — the one to surface inline
    as a faint hint right under the user's input line.

    An empty string means "no hint to show".
    """
    hits = suggest(text, commands)
    return hits[0] if hits else ""


__all__ = [
    "DEFAULT_COMMANDS",
    "is_slash_prefix",
    "suggest",
    "primary_suggestion",
]
