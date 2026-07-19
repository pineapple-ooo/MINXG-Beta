"""
multiligua_cli/themes.py — MINXG Theme System

Provides customizable themes for the TUI with different
color schemes, layouts, and visual styles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
#  Theme Definitions
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Theme:
    """A complete theme definition."""
    name: str
    display_name: str
    description: str

    # Primary colors
    bg_deep: str = "rgb(10,30,80)"       # Deep background
    bg_panel: str = "rgb(16,42,105)"     # Panel background
    accent: str = "bright_cyan"           # Primary accent
    secondary: str = "deep_sky_blue3"    # Secondary color
    dim_color: str = "rgb(45,85,155)"    # Dim text
    gold: str = "gold3"                  # Brand accent

    # Message styles
    user_prefix: str = "bold bright_green"
    user_bg: str = "rgb(0,40,0)"
    ai_prefix: str = "bold bright_cyan"
    ai_bg: str = "rgb(0,20,40)"
    system_prefix: str = "bold yellow"

    # Border styles
    border_style: str = "bright_blue"
    panel_border: str = "blue"

    # Status bar
    status_bg: str = "rgb(5,15,40)"
    status_text: str = "dim silver"

    # Special
    error_color: str = "bright_red"
    success_color: str = "bright_green"
    warning_color: str = "yellow"

    # Layout
    compact_mode: bool = False
    show_timestamps: bool = True
    show_token_count: bool = True


# ── Built-in Themes ──────────────────────────────────────────────

THEMES: Dict[str, Theme] = {
    "blue-premium": Theme(
        name="blue-premium",
        display_name="Blue Premium",
        description="Deep navy with cyan accents — the default MINXG look",
        bg_deep="rgb(10,30,80)",
        bg_panel="rgb(16,42,105)",
        accent="bright_cyan",
        secondary="deep_sky_blue3",
        dim_color="rgb(45,85,155)",
        gold="gold3",
    ),

    "dark-modern": Theme(
        name="dark-modern",
        display_name="Dark Modern",
        description="Pure black with vibrant accents — easy on the eyes",
        bg_deep="rgb(0,0,0)",
        bg_panel="rgb(15,15,15)",
        accent="bright_magenta",
        secondary="bright_blue",
        dim_color="rgb(80,80,80)",
        gold="bright_yellow",
    ),

    "matrix": Theme(
        name="matrix",
        display_name="Matrix",
        description="Green on black — for the classic hacker feel",
        bg_deep="rgb(0,10,0)",
        bg_panel="rgb(0,20,0)",
        accent="bright_green",
        secondary="green",
        dim_color="rgb(0,80,0)",
        gold="bright_yellow",
        user_prefix="bold bright_green",
        user_bg="rgb(0,30,0)",
        ai_prefix="bold green",
        ai_bg="rgb(0,20,0)",
    ),

    "warm-sunset": Theme(
        name="warm-sunset",
        display_name="Warm Sunset",
        description="Warm oranges and purples — cozy and inviting",
        bg_deep="rgb(40,10,30)",
        bg_panel="rgb(60,20,40)",
        accent="bright_magenta",
        secondary="bright_red",
        dim_color="rgb(100,50,80)",
        gold="bright_yellow",
        user_prefix="bold bright_yellow",
        user_bg="rgb(40,30,0)",
        ai_prefix="bold bright_magenta",
        ai_bg="rgb(30,0,30)",
    ),

    "minimal": Theme(
        name="minimal",
        display_name="Minimal",
        description="No background colors — maximum readability",
        bg_deep="",
        bg_panel="",
        accent="bold cyan",
        secondary="cyan",
        dim_color="dim",
        gold="bold yellow",
        user_prefix="bold green",
        user_bg="",
        ai_prefix="bold blue",
        ai_bg="",
    ),

    "high-contrast": Theme(
        name="high-contrast",
        display_name="High Contrast",
        description="Maximum contrast for accessibility",
        bg_deep="rgb(0,0,0)",
        bg_panel="rgb(20,20,20)",
        accent="bright_white",
        secondary="bright_yellow",
        dim_color="bright_black",
        gold="bright_yellow",
        user_prefix="bold bright_white",
        user_bg="rgb(30,30,30)",
        ai_prefix="bold bright_yellow",
        ai_bg="rgb(20,20,0)",
    ),

    "nord": Theme(
        name="nord",
        display_name="Nord",
        description="Nordic-inspired cool blues and grays",
        bg_deep="rgb(47,52,64)",
        bg_panel="rgb(59,66,82)",
        accent="bright_cyan",
        secondary="bright_blue",
        dim_color="rgb(94,105,122)",
        gold="bright_yellow",
    ),

    "dracula": Theme(
        name="dracula",
        display_name="Dracula",
        description="Dark with purple/pink accents — popular dev theme",
        bg_deep="rgb(40,42,54)",
        bg_panel="rgb(68,71,90)",
        accent="bright_magenta",
        secondary="bright_cyan",
        dim_color="rgb(98,114,164)",
        gold="bright_yellow",
    ),
}

# Default theme
DEFAULT_THEME = "blue-premium"

# Theme order for display
THEME_ORDER = [
    "blue-premium",
    "dark-modern",
    "matrix",
    "warm-sunset",
    "minimal",
    "high-contrast",
    "nord",
    "dracula",
]


# ═══════════════════════════════════════════════════════════════════
#  Theme Manager
# ═══════════════════════════════════════════════════════════════════

_current_theme: Optional[str] = None


def get_theme(name: Optional[str] = None) -> Theme:
    """Get a theme by name, or the current theme."""
    if name is None:
        name = _current_theme or DEFAULT_THEME
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def set_theme(name: str) -> bool:
    """Set the current theme. Returns True if successful."""
    global _current_theme
    if name in THEMES:
        _current_theme = name
        return True
    return False


def get_current_theme_name() -> str:
    """Get the current theme name."""
    return _current_theme or DEFAULT_THEME


def list_themes() -> List[Dict[str, str]]:
    """List all available themes."""
    return [
        {
            "name": t.name,
            "display_name": t.display_name,
            "description": t.description,
            "is_current": t.name == get_current_theme_name(),
        }
        for t in [THEMES[k] for k in THEME_ORDER if k in THEMES]
    ]


def print_themes(console=None) -> None:
    """Print available themes."""
    if console is None:
        try:
            from multiligua_cli.utils import console
        except ImportError:
            print("\nAvailable themes:")
            for t in list_themes():
                current = " (current)" if t["is_current"] else ""
                print(f"  {t['name']:20}  {t['display_name']}{current}")
                print(f"  {' ' * 22}  {t['description']}")
            return

    try:
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
    except ImportError:
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
    )
    table.add_column("Theme", style="bold", width=18)
    table.add_column("Name", style="cyan", width=15)
    table.add_column("Description")
    table.add_column("Active", width=8)

    for t in list_themes():
        active = "[bold green]✓[/bold green]" if t["is_current"] else ""
        table.add_row(t["name"], t["display_name"], t["description"], active)

    console.print(Panel(
        table,
        title="[bold gold3]◆  Themes[/bold gold3]",
        border_style="bright_blue",
        padding=(0, 1),
    ))


# ═══════════════════════════════════════════════════════════════════
#  Custom Theme Support
# ═══════════════════════════════════════════════════════════════════

def create_custom_theme(
    name: str,
    display_name: str,
    description: str,
    **kwargs,
) -> Theme:
    """Create a custom theme."""
    theme = Theme(
        name=name,
        display_name=display_name,
        description=description,
    )
    for key, value in kwargs.items():
        if hasattr(theme, key):
            setattr(theme, key, value)
    return theme


def save_theme(theme: Theme, path: str) -> None:
    """Save a theme to a JSON file."""
    import json
    from pathlib import Path

    data = {
        "name": theme.name,
        "display_name": theme.display_name,
        "description": theme.description,
        "colors": {
            k: v for k, v in theme.__dict__.items()
            if k not in ("name", "display_name", "description")
        },
    }

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_theme(path: str) -> Optional[Theme]:
    """Load a theme from a JSON file."""
    import json
    from pathlib import Path

    if not Path(path).exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return create_custom_theme(
        name=data.get("name", "custom"),
        display_name=data.get("display_name", "Custom"),
        description=data.get("description", "Custom theme"),
        **data.get("colors", {}),
    )
