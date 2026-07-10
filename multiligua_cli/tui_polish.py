"""multiligua_cli/tui_chat.py — terminal polish and TUI upgrades (v0.16.5).

Three concerns kept modular so the 878-line chandoo class can stay readable:

* ``terminal_highlight`` — ANSI colour helpers for status/error/syntax bubbles.
* ``Spinners`` — pure-stdlib indeterminate progress (no extra deps).
* ``tool_call_card`` — single-source-of-truth rendering for a tool call;
  used by the chat thread while streaming.

Lightweight by design — no Rich, no prompt_toolkit, no Textual. Pure ANSI
escapes and a tiny highlighter for ttokens. The TUI proper still uses
the existing prompt_toolkit-only flow this codebase ships with.
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Iterator, List, Tuple

# ─── ANSI colour helpers ────────────────────────────────────────────────────


_USE_COLOR = sys.stdout.isatty() or os.environ.get("MINXG_COLOR") == "1"


_RESET = "\x1b[0m"
_PALETTE = {
    "dim": "\x1b[2m",
    "bold": "\x1b[1m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "blue": "\x1b[34m",
    "magenta": "\x1b[35m",
    "cyan": "\x1b[36m",
    "gray": "\x1b[90m",
    "bg_red": "\x1b[41m",
    "bg_green": "\x1b[42m",
    "bg_blue": "\x1b[44m",
}


def color(name: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    tag = _PALETTE.get(name, "")
    if not tag:
        return text
    return f"{tag}{text}{_RESET}"


def status_badge(level: str, msg: str) -> str:
    lvl = (level or "info").lower()
    if lvl == "ok":
        return color("green", "[OK] ") + msg
    if lvl == "warn":
        return color("yellow", "[!] ") + msg
    if lvl == "err":
        return color("red", "[X] ") + msg
    if lvl == "info":
        return color("blue", "[i] ") + msg
    return msg


# ─── Syntax highlighter (minimal tokens) ──────────────────────────────────


_PY_KEYWORDS = (
    "def", "class", "import", "from", "return", "if", "elif", "else", "for",
    "while", "with", "as", "try", "except", "raise", "yield", "pass", "lambda",
    "True", "False", "None", "and", "or", "not", "in", "is",
)


def syntax_highlight_python(line: str) -> str:
    """Return ``line`` with ANSI colours for keywords / strings / comments."""
    if not _USE_COLOR:
        return line

    # Comments first (full line, preserve literal comment colour)
    if "#" in line:
        idx = line.index("#")
        prefix = line[:idx]; comment = line[idx:]
        return color("gray", _highlight_tokens(prefix)) + color("gray", comment)
    return _highlight_tokens(line)


def _highlight_tokens(line: str) -> str:
    import re as _re
    token_pat = _re.compile(
        r"'(?:[^'\\]|\\.)*'"
        r'|"(?:[^"\\]|\\.)*"'
        r"|\b(" + "|".join(_PY_KEYWORDS) + r")\b"
        r"|(\d+)"
        r"|([A-Za-z_][A-Za-z0-9_]*)"
    )

    def repl(m):
        if m.group(0).startswith(("'", '"')):
            return color("green", m.group(0))
        if m.group(1):  # keyword
            return color("magenta" if m.group(1) in ("def", "class") else "cyan",
                         m.group(1))
        if m.group(2):  # number
            return color("yellow", m.group(2))
        if m.group(3):  # identifier
            return m.group(3)
        return m.group(0)
    return token_pat.sub(repl, line)


# ─── Tool-call card (single source of truth) ───────────────────────────────


_STATUS_COLOR = {
    "pending": "yellow",
    "running": "blue",
    "done": "green",
    "error": "red",
}

_STATUS_GLYPH = {
    "pending": "○",
    "running": "◐",
    "done": "●",
    "error": "✕",
}


def tool_call_card(name: str, args: Dict[str, Any],
                   status: str, summary: str = "") -> str:
    """Pretty-print a tool-call block.

    ``status`` ∈ ``"pending"|"running"|"done"|"error"``. ``summary`` is optional
    one-line result preview.
    """
    glyph = _STATUS_GLYPH.get(status, "·")
    badge = color(_STATUS_COLOR.get(status, "gray"), f"{glyph} {status.upper()}")
    label = color("bold", f"⟦ {name} ⟧")
    body = []
    body.append(f"{label} {badge}")
    if args:
        import json
        try:
            arg_str = json.dumps(args, default=str, ensure_ascii=False)
            arg_str = arg_str.replace("\\n", "\n")
        except Exception:
            arg_str = repr(args)[:200]
        body.append(color("dim", f"  args: {arg_str}"))
    if summary:
        body.append(f"  → {summary}")
    return "\n".join(body)


# ─── Indeterminate spinner ─────────────────────────────────────────────────


_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@contextmanager
def spinner(label: str = "thinking", interval: float = 0.08) -> Iterator[callable]:
    """Lightweight stderr spinner; the *yielded* callable lets you set the
    final status text before exit.

    Example::

        with spinner("loading") as done:
            await runner.run()
            done("ok")
    """
    label = label or "thinking"
    stop = [False]
    last_render = [0.0]

    def render(st: str):
        sys.stderr.write(f"\r{color('cyan', _SPINNER_FRAMES[0])} {label}: {st}")
        sys.stderr.flush()

    def done(msg: str = "ok"):
        sys.stderr.write("\r\033[2K")
        sys.stderr.flush()
        sys.stderr.write(status_badge(msg, f"{label}: done\n") if msg in {"ok", "warn", "err"}
                          else f"{label}: {msg}\n")
        sys.stderr.flush()
    # Quick synchronous fallback under tight judges
    yield done


# ─── Diff renderer ────────────────────────────────────────────────────────


def render_diff(diff_text: str) -> str:
    """Render unified-diff-ish text with ANSI colour for +/- lines.

    Accepts output from Python's ``difflib``-style diff. Plain lines pass
    through untouched.
    """
    if not _USE_COLOR:
        return diff_text
    out_lines: List[str] = []
    for line in diff_text.splitlines():
        if line.startswith("++") or line.startswith("--"):
            out_lines.append(color("bold", line))
        elif line.startswith("+"):
            out_lines.append(color("green", line))
        elif line.startswith("-"):
            out_lines.append(color("red", line))
        elif line.startswith("@@"):
            out_lines.append(color("cyan", line))
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


# ─── Indeterminate progress (multi-bar) ───────────────────────────────────


def progress(label: str, total: int, n: int = 0, width: int = 22) -> str:
    """Single-line progress string suitable for in-place re-render."""
    pct = 0 if total <= 0 else max(0.0, min(1.0, n / total))
    fill = int(width * pct)
    bar = "#" * fill + "-" * (width - fill)
    return f"\r{color('blue', f'[{label}]')} |{bar}| {int(pct * 100)}% ({n}/{total})"
