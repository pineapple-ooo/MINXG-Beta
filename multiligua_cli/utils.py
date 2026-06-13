"""
multiligua_cli/utils.py — Shared utilities for the MINXG CLI.

Extracted from main.py to keep command modules lean.
All UI helpers, config access, and process helpers live here.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any

# ── Version ──────────────────────────────────────────────────────────────────
__version__ = "1.0.0"

# ── i18n (lazy import to avoid circular) ─────────────────────────────────────

def _t(key: str, **kwargs) -> str:
    """Lazy i18n lookup."""
    try:
        from multiligua_cli.i18n import T
        return T(key, **kwargs)
    except Exception:
        return key

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("minxg")

# ── Rich detection ───────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None

# ── ANSI Colors (fallback when Rich not available) ───────────────────────────


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"


def colorize(text: str, *styles: str) -> str:
    """Wrap text with ANSI codes (no-op when Rich is active)."""
    if HAS_RICH:
        return text
    return "".join(styles) + text + Colors.RESET


# ── Project path helpers ─────────────────────────────────────────────────────


def get_project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def get_config_path() -> Path:
    return get_project_root() / "config.yaml"


def config_exists() -> bool:
    return get_config_path().exists()


def load_config() -> Dict[str, Any]:
    """Load YAML config, returning empty dict on any failure."""
    path = get_config_path()
    if path.exists():
        try:
            import yaml

            with open(path) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


# ── Config-check decorator ───────────────────────────────────────────────────


def ensure_config(func):
    """Decorator: if config.yaml is missing, run setup wizard first."""

    def wrapper(*args, **kwargs):
        if not config_exists():
            if HAS_RICH:
                console.print(
                    Panel.fit(
                        "[yellow]No configuration found![/yellow]\n"
                        "Running setup wizard first...",
                        title="Config Required",
                        box=box.ROUNDED,
                    )
                )
            else:
                print(
                    colorize(
                        "⚠ No configuration found! Running setup wizard first...",
                        Colors.YELLOW,
                    )
                )

            from multiligua_cli.setup import run_setup as setup_main

            result = setup_main()
            if result != 0:
                print_error("Setup failed. Cannot proceed.")
                return result

        return func(*args, **kwargs)

    return wrapper


# ── UI helpers ───────────────────────────────────────────────────────────────


def print_banner() -> None:
    banner = f"""\n╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║                    ███╗   ███╗██╗███╗   ██╗██╗  ██╗ ██████╗        ║
║                    ████╗ ████║██║████╗  ██║╚██╗██╔╝██╔════╝        ║
║                    ██╔████╔██║██║██╔██╗ ██║ ╚███╔╝ ██║  ███╗       ║
║                    ██║╚██╔╝██║██║██║╚██╗██║ ██╔██╗ ██║   ██║       ║
║                    ██║ ╚═╝ ██║██║██║ ╚████║██╔╝ ██╗╚██████╔╝       ║
║                    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝        ║
║                                                                      ║
║              MINXG — Multi-Language AI Orchestration                 ║
║                                                                      ║
║                           v{__version__}                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    if HAS_RICH:
        console.print(banner, style="cyan bold")
    else:
        print(colorize(banner, Colors.CYAN, Colors.BOLD))


def print_error(msg: str) -> None:
    if HAS_RICH:
        console.print(f"[red]✗ {msg}[/red]")
    else:
        print(colorize(f"✗ {msg}", Colors.RED))


def print_success(msg: str) -> None:
    if HAS_RICH:
        console.print(f"[green]✓ {msg}[/green]")
    else:
        print(colorize(f"✓ {msg}", Colors.GREEN))


def print_info(msg: str) -> None:
    if HAS_RICH:
        console.print(f"[yellow]ℹ {msg}[/yellow]")
    else:
        print(colorize(f"ℹ {msg}", Colors.YELLOW))


def print_dim(msg: str) -> None:
    if HAS_RICH:
        console.print(f"[dim]{msg}[/dim]")
    else:
        print(colorize(msg, Colors.DIM))


def print_warning(msg: str) -> None:
    if HAS_RICH:
        console.print(f"[orange3]⚠ {msg}[/orange3]")
    else:
        print(colorize(f"⚠ {msg}", Colors.YELLOW, Colors.BOLD))


# ── Process title ────────────────────────────────────────────────────────────


def set_process_title() -> None:
    """Set process title for ps/top visibility. Non-fatal."""
    try:
        import setproctitle

        setproctitle.setproctitle("minxg")
        return
    except ImportError:
        pass

    try:
        import ctypes

        if sys.platform == "linux":
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            libc.prctl(15, b"minxg", 0, 0, 0)
        elif sys.platform == "darwin":
            libc = ctypes.CDLL("libc.dylib", use_errno=True)
            try:
                libc.prctl(15, b"minxg")
            except Exception:
                pass
    except Exception:
        pass
