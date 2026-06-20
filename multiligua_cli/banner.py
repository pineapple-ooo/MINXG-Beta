"""
multiligua_cli/banner.py — ASCII banner for MINXG.

Used by the TUI chat, the install script, the setup wizard, and any
other surface that wants a recognisable MINXG header. The same banner
shows whether rich is installed or not — the figures are made of
ordinary ASCII so they survive in plain pipes and log files.
"""

from __future__ import annotations

from typing import Optional


# MINXG wordmark — blocky 5-row figure that fits an 80-col TTY.
# Designed to read clearly even when the user's terminal has
# anti-aliased fonts and weird metric ratios.
_BANNER_LINES = [
    r"███╗   ███╗██╗███╗   ██╗██╗  ██╗ ██████╗ ",
    r"████╗ ████║██║████╗  ██║╚██╗██╔╝██╔════╝ ",
    r"██╔████╔██║██║██╔██╗ ██║ ╚███╔╝ ██║  ███╗",
    r"██║╚██╔╝██║██║██║╚██╗██║ ██╔██╗ ██║   ██║",
    r"██║ ╚═╝ ██║██║██║ ╚████║██╔╝ ██╗╚██████╔╝",
    r"╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ",
]


SUBTITLE = "five-pillar worker platform  ·  v{version}"


def banner_figure(color: Optional[str] = None) -> str:
    """Return the MINXG ASCII wordmark as plain text."""
    if not color:
        return "\n".join(_BANNER_LINES)
    return "\n".join(f"{color}{line}\033[0m" for line in _BANNER_LINES)


def banner_block(version: str = "", subtitle_color: str = "\033[38;5;245m") -> str:
    """Return a full banner block — figure + subtitle — as a string."""
    fig = banner_figure()
    if version:
        subtitle = f"  {SUBTITLE.format(version=version)}"
    else:
        subtitle = ""
    if subtitle:
        if subtitle_color:
            subtitle = f"{subtitle_color}{subtitle}\033[0m"
        return f"{fig}\n{subtitle}"
    return fig


def rules(width: int = 60, char: str = "-", color: Optional[str] = None) -> str:
    """Return a horizontal separator line of `width` cells."""
    line = char * width
    if color:
        return f"{color}{line}\033[0m"
    return line


def titled_panel(title: str, body: str, width: int = 60,
                 border_color: Optional[str] = None) -> str:
    """Return a tiny boxed-panel string with a centred title."""
    bar_top = f"+{'-' * (width - 2)}+"
    bar_bot = f"+{'-' * (width - 2)}+"
    title_line = f"| {title.center(width - 4)} |"
    body_lines = body.splitlines() or [""]
    body_block = "\n".join(f"| {ln.ljust(width - 4)} |" for ln in body_lines)
    block = "\n".join([bar_top, title_line, *body_block.splitlines(), bar_bot])
    if border_color:
        return "\n".join(border_color + ln + "\033[0m" for ln in block.splitlines())
    return block
