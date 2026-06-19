"""
MINXG Wizard UI Engine v2.0

Design Philosophy:
  - No Agent-framework UI style
  - MINXG style: distinct colors, high info density, graphical progress bar
  - All output text follows user language
  - Supports Rich and ANSI rendering modes
"""

import os
import sys
from typing import Optional, List


try:
    from multiligua_cli.i18n import T, set_lang, get_lang, LANGUAGES, LANG_NAMES, LANG_CODES
except ImportError:
    def T(key, **kw): return key
    def set_lang(c): pass
    def get_lang(): return "en"
    LANGUAGES = {"en": {"flag": "EN", "name": "English", "native": "English"}}
    LANG_NAMES = ["English"]
    LANG_CODES = ["en"]


try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


try:
    import readchar
    HAS_READCHAR = True
except ImportError:
    HAS_READCHAR = False





class Colors:
    """MINXG colors — blue-violet base + gold accent + green confirm"""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"

    INDIGO  = "\033[38;5;99m"
    VIOLET  = "\033[38;5;183m"
    AMETHYST = "\033[38;5;147m"

    GOLD    = "\033[38;5;220m"
    TEAL    = "\033[38;5;37m"
    SLATE   = "\033[38;5;245m"
    EMERALD = "\033[38;5;82m"
    CORAL   = "\033[38;5;209m"
    AMBER   = "\033[38;5;214m"
    SILVER  = "\033[38;5;250m"

    BG_INDIGO = "\033[48;5;99m"
    BG_VIOLET = "\033[48;5;183m"






def clear_screen():
    """Clear screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def _ansi(text: str, *styles) -> str:
    if HAS_RICH:
        return text
    return "".join(styles) + text + Colors.RESET


def print_banner():
    try:
        from minxg import VERSION
        ver = VERSION
    except Exception:
        ver = "0.0.0+unknown"
    lang = get_lang()
    tagline = T("brand_full")

    if HAS_RICH:
        banner_text = Text()

        art = [
            "    ██╗███╗   ██╗██╗  ██╗ ██████╗ ",
            "    ██║████╗  ██║╚██╗██╔╝██╔════╝ ",
            "    ██║██╔██╗ ██║ ╚███╔╝ ██║  ███╗",
            "    ██║██║╚██╗██║ ██╔██╗ ██║   ██║",
            "    ██║██║ ╚████║██╔╝ ██╗╚██████╔╝",
            "    ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ",
        ]
        for line in art:
            banner_text.append(line + "\n", style="bold violet")

        banner_text.append(f"\n  {tagline}", style="bold gold3")
        banner_text.append(f"  v{ver}\n\n", style="italic dim")

        console.print(Panel(banner_text, box=box.HEAVY, border_style="bright_blue", padding=(1, 2)))
    else:
        art = f"""
{_ansi("    ██╗███╗   ██╗██╗  ██╗ ██████╗ ", Colors.INDIGO, Colors.BOLD)}
{_ansi("    ██║████╗  ██║╚██╗██╔╝██╔════╝ ", Colors.VIOLET, Colors.BOLD)}
{_ansi("    ██║██╔██╗ ██║ ╚███╔╝ ██║  ███╗", Colors.AMETHYST, Colors.BOLD)}
{_ansi("    ██║██║╚██╗██║ ██╔██╗ ██║   ██║", Colors.INDIGO, Colors.BOLD)}
{_ansi("    ██║██║ ╚████║██╔╝ ██╗╚██████╔╝", Colors.VIOLET, Colors.BOLD)}
{_ansi("    ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ", Colors.AMETHYST, Colors.BOLD)}

  {_ansi(tagline, Colors.GOLD, Colors.BOLD)}
  {_ansi(f"v{ver}", Colors.SLATE)}
"""
        print(art)


def print_step_progress(step: int, total: int, title: str):
    filled = int(30 * step / total)
    bar_fill = "█" * filled
    bar_empty = "░" * (30 - filled)

    if HAS_RICH:
        progress_text = Text()
        progress_text.append(f"  [{step}/{total}] ", style="bold teal")
        progress_text.append(bar_fill, style="bold gold3")
        progress_text.append(bar_empty, style="dim")
        progress_text.append(f" {title}", style="bold gold3")
        console.print(progress_text)
        console.print(f"  {_ansi('─' * 50, Colors.SLATE)}")
    else:
        bar = _ansi(bar_fill, Colors.GOLD, Colors.BOLD) + _ansi(bar_empty, Colors.SLATE)
        print(f"  {_ansi(f'[{step}/{total}]', Colors.TEAL, Colors.BOLD)} {bar} {_ansi(title, Colors.GOLD, Colors.BOLD)}")
        print(f"  {_ansi('─' * 50, Colors.SLATE)}")


def _truncate_desc(desc: str, max_len: int = 28) -> str:
    """Cap a description so the line stays singular on Termux."""
    if not desc:
        return ""
    if len(desc) <= max_len:
        return desc
    if max_len <= 1:
        return desc[:max_len]
    return desc[: max_len - 1] + "\u2026"


def print_option_item(selected: bool, text: str, desc: str = "",
                      indent: int = 2) -> None:
    """Render one menu option on a SINGLE line.

    Long descriptions are truncated so the layout survives narrow
    terminals (Termux ~ 80 cols).
    """
    marker = "\u25c8" if selected else "\u25c7"
    short_desc = _truncate_desc(desc)
    if HAS_RICH:
        style = "bold gold3" if selected else "dim"
        line = f"{' ' * indent}[{style}]{marker} {text}[/{style}]"
        if short_desc:
            sub = "italic teal" if selected else "italic dim"
            line += f"  [{sub}]{short_desc}[/{sub}]"
        console.print(line)
    else:
        if selected:
            head = _ansi(f"{marker} {text}", Colors.GOLD, Colors.BOLD)
            tail = _ansi(short_desc, Colors.TEAL,
                         Colors.ITALIC) if short_desc else ""
        else:
            head = _ansi(f"{marker} {text}", Colors.SLATE)
            tail = _ansi(short_desc, Colors.DIM) if short_desc else ""
        if tail:
            print(f"{' ' * indent}{head}  {tail}")
        else:
            print(f"{' ' * indent}{head}")


def print_success(msg: str):
    if HAS_RICH:
        console.print(f"  {_ansi('✓', Colors.EMERALD)} [bold emerald]{msg}[/bold emerald]")
    else:
        print(f"  {_ansi('✓', Colors.EMERALD, Colors.BOLD)} {_ansi(msg, Colors.EMERALD)}")


def print_error(msg: str):
    if HAS_RICH:
        console.print(f"  {_ansi('✗', Colors.CORAL)} [bold coral]{msg}[/bold coral]")
    else:
        print(f"  {_ansi('✗', Colors.CORAL, Colors.BOLD)} {_ansi(msg, Colors.CORAL)}")


def print_info(msg: str):
    if HAS_RICH:
        console.print(f"  {_ansi('ℹ', Colors.TEAL)} [teal]{msg}[/teal]")
    else:
        print(f"  {_ansi('ℹ', Colors.TEAL)} {_ansi(msg, Colors.TEAL)}")


def print_warning(msg: str):
    if HAS_RICH:
        console.print(f"  {_ansi('⚠', Colors.AMBER)} [bold amber]{msg}[/bold amber]")
    else:
        print(f"  {_ansi('⚠', Colors.AMBER, Colors.BOLD)} {_ansi(msg, Colors.AMBER)}")


def print_section(title: str):
    if HAS_RICH:
        console.print(f"\n  {_ansi('▸', Colors.AMETHYST)} [bold amethyst]{title}[/bold amethyst]")
    else:
        print(f"\n  {_ansi('▸', Colors.AMETHYST, Colors.BOLD)} {_ansi(title, Colors.AMETHYST)}")


def print_kv(key: str, value: str, indent: int = 4):
    if HAS_RICH:
        console.print(f"{' ' * indent}[gold3]{key}:[/gold3] [silver]{value}[/silver]")
    else:
        print(f"{' ' * indent}{_ansi(f'{key}:', Colors.GOLD)} {_ansi(value, Colors.SILVER)}")


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

class MinxgMenu:
    """MINXG Menu - interactive selection widget."""

    def __init__(self, title: str, options: List[str], descriptions: List[str] = None):
        self.title = title
        self.options = options
        self.descriptions = descriptions or [""] * len(options)
        self.selected = 0
        self.running = True

    def _render(self):
        clear_screen()
        if HAS_RICH:
            console.print(f"\n  [bold gold3]{self.title}[/bold gold3]\n")
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                print_option_item(i == self.selected, opt, desc)
            nav_hint = T("wizard_nav_hint")
            console.print(f"\n  [dim]{nav_hint}[/dim]")
        else:
            print(f"\n  {_ansi(self.title, Colors.GOLD, Colors.BOLD)}\n")
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                print_option_item(i == self.selected, opt, desc)
            print(f"\n  {_ansi(T('wizard_nav_hint'), Colors.SLATE)}")

    def run(self) -> Optional[int]:
        # Path 1: readchar unavailable — fall back to plain numbered input.
        if not HAS_READCHAR:
            self._render()
            while True:
                try:
                    for i, opt in enumerate(self.options):
                        print(f"  {i + 1}. {opt}")
                    raw = input("  Enter choice: ")
                    raw = raw.strip()
                    if raw.lower() == "q":
                        return None
                    idx = int(raw) - 1
                    if 0 <= idx < len(self.options):
                        return idx
                    print_error(T("err_number_range", min=1, max=len(self.options)))
                except ValueError:
                    print_error(T("err_invalid_input"))
                except (KeyboardInterrupt, EOFError):
                    return None

        # Path 2: interactive arrow-key navigation via readchar.
        self._render()
        while self.running:
            key = readchar.readkey()
            if key == readchar.key.UP:
                self.selected = (self.selected - 1) % len(self.options)
                self._render()
            elif key == readchar.key.DOWN:
                self.selected = (self.selected + 1) % len(self.options)
                self._render()
            elif key == readchar.key.ENTER:
                return self.selected
            elif key.lower() == 'q':
                return None






def prompt(question: str, default: str = None, password: bool = False) -> str:
    display = f"{question} [{default}]: " if default else f"{question}: "

    while True:
        try:
            if HAS_RICH:
                value = console.input(f"[gold3]{display}[/gold3]")
            else:
                value = input(_ansi(display, Colors.GOLD))
            value = value.strip()
            if value:
                return value
            if default:
                return default
            if not password:
                return ""
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(1)


def prompt_yes_no(question: str, default: bool = True) -> bool:
    yes_text = T("yes")
    no_text = T("no")
    menu = MinxgMenu(question, [yes_text, no_text])
    result = menu.run()
    if result is None:
        return default
    return result == 0


def prompt_choice(question: str, choices: List[str], descriptions: List[str] = None,
                  default: int = 0) -> int:
    menu = MinxgMenu(question, choices, descriptions)
    menu.selected = default
    result = menu.run()
    if result is None:
        return default
    return result
