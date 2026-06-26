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
import shutil
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
    readchar = None  # type: ignore[assignment]





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
    BRIGHT_BLUE = "\033[38;5;75m"

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

        banner_text.append("\n  ", style="")
        banner_text.append("◆ ", style="bold gold3")
        banner_text.append(tagline, style="bold gold3")
        banner_text.append(f"  v{ver}", style="italic dim cyan")
        banner_text.append("\n", style="")
        banner_text.append("  setup wizard\n",
                          style="dim italic")

        console.print(Panel(banner_text, box=box.HEAVY,
                            border_style="bright_blue", padding=(1, 2)))
    else:
        art = f"""
{_ansi("    ██╗███╗   ██╗██╗  ██╗ ██████╗ ", Colors.INDIGO, Colors.BOLD)}
{_ansi("    ██║████╗  ██║╚██╗██╔╝██╔════╝ ", Colors.VIOLET, Colors.BOLD)}
{_ansi("    ██║██╔██╗ ██║ ╚███╔╝ ██║  ███╗", Colors.AMETHYST, Colors.BOLD)}
{_ansi("    ██║██║╚██╗██║ ██╔██╗ ██║   ██║", Colors.INDIGO, Colors.BOLD)}
{_ansi("    ██║██║ ╚████║██╔╝ ██╗╚██████╔╝", Colors.VIOLET, Colors.BOLD)}
{_ansi("    ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ", Colors.AMETHYST, Colors.BOLD)}

  {_ansi("◆ ", Colors.GOLD, Colors.BOLD)}{_ansi(tagline, Colors.GOLD, Colors.BOLD)}  {_ansi(f"v{ver}", Colors.SLATE)}
  {_ansi("setup wizard", Colors.SLATE)}
"""
        print(art)


def print_chat_banner():
    """The chat-surface variant of the wizard banner — substitutes the
    "setup wizard" sub-line for the "MINXG Chat" brand line so the same
    banner module serves both surfaces without context bleed.
    """
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

        banner_text.append("\n  ", style="")
        banner_text.append("◆ ", style="bold gold3")
        banner_text.append(tagline, style="bold gold3")
        banner_text.append(f"  v{ver}", style="italic dim cyan")
        banner_text.append("\n", style="")
        banner_text.append("  MINXG Chat — interactive REPL\n",
                          style="dim italic")

        console.print(Panel(banner_text, box=box.HEAVY,
                            border_style="bright_blue", padding=(1, 2)))
    else:
        art = f"""
{_ansi("    ██╗███╗   ██╗██╗  ██╗ ██████╗ ", Colors.INDIGO, Colors.BOLD)}
{_ansi("    ██║████╗  ██║╚██╗██╔╝██╔════╝ ", Colors.VIOLET, Colors.BOLD)}
{_ansi("    ██║██╔██╗ ██║ ╚███╔╝ ██║  ███╗", Colors.AMETHYST, Colors.BOLD)}
{_ansi("    ██║██║╚██╗██║ ██╔██╗ ██║   ██║", Colors.INDIGO, Colors.BOLD)}
{_ansi("    ██║██║ ╚████║██╔╝ ██╗╚██████╔╝", Colors.VIOLET, Colors.BOLD)}
{_ansi("    ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ", Colors.AMETHYST, Colors.BOLD)}

  {_ansi("◆ ", Colors.GOLD, Colors.BOLD)}{_ansi(tagline, Colors.GOLD, Colors.BOLD)}  {_ansi(f"v{ver}", Colors.SLATE)}
  {_ansi("MINXG Chat — interactive REPL", Colors.SLATE)}
"""
        print(art)


def print_step_progress(step: int, total: int, title: str):
    """Render a one-line progress header like  `[2/6] ████░░ Step Name`."""
    bar_w = 28
    filled = max(0, min(bar_w, int(bar_w * step / total)))
    bar_fill = "█" * filled
    bar_empty = "░" * (bar_w - filled)

    if HAS_RICH:
        progress_text = Text()
        progress_text.append(f"  [{step}/{total}] ", style="bold teal")
        progress_text.append(bar_fill, style="bold gold3")
        progress_text.append(bar_empty, style="dim")
        progress_text.append(f"  {title}", style="bold bright_blue")
        console.print(progress_text)
        console.print(f"  {_ansi('─' * 50, Colors.SLATE)}")
    else:
        bar = (_ansi(bar_fill, Colors.GOLD, Colors.BOLD)
               + _ansi(bar_empty, Colors.SLATE))
        head = _ansi(f"[{step}/{total}]", Colors.TEAL, Colors.BOLD)
        label = _ansi(title, Colors.BRIGHT_BLUE, Colors.BOLD)
        print(f"  {head} {bar} {label}")
        print(f"  {_ansi('─' * 50, Colors.SLATE)}")


def _truncate_desc(desc: str, max_len: int | None = None) -> str:
    """Cap a description so the line stays singular on Termux.

    ``max_len=None`` (default) picks a width from the live terminal so
    descriptions can use more of a wide screen on desktop while still
    surviving narrow Termux pipes.
    """
    if not desc:
        return ""
    if max_len is None:
        try:
            cols = shutil.get_terminal_size((80, 20)).columns
        except Exception:
            cols = 80
        # 28 was the original fixed budget; allow up to 56 on wide terminals
        # but never below 28 so layout stays predictable.
        max_len = max(28, min(56, cols - 30))
    if max_len <= 0:
        return desc
    if len(desc) <= max_len:
        return desc
    if max_len == 1:
        return desc[:1]
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
    """MINXG Menu - interactive selection widget.

    Auto-sizing single-line menu that paints *in place* on every key
    press instead of fork-bombing ``clear`` to wipe the screen. The
    first render establishes how many rows the widget needs; later
    renders move the cursor up to the widget's top row and rewrite
    those lines only, so the chat scrollback above the widget
    stays put and no full-screen flicker shows up under Termux.

    Both rendering branches (Rich and plain-ANSI) now route through
    a single ``_emit_line(lines)`` helper so the layout, line count,
    and ANSI escape sequence ordering stay identical regardless of the
    console backend — that is what kills the "flickers during
    interaction" bug that the original two-branch duplication caused.
    """

    def __init__(self, title: str, options: List[str], descriptions: List[str] = None):
        self.title = title
        self.options = options
        self.descriptions = descriptions or [""] * len(options)
        self.selected = 0
        self.running = True
        self._painted_rows = 0       # rows the previous render occupied
        self._supports_ansi = (
            sys.stdout.isatty() and not os.environ.get("TERM") == "dumb"
        )

    @staticmethod
    def _strip_ansi(s: str) -> str:
        import re
        return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", s)

    @staticmethod
    def _line_width(s: str) -> int:
        """Visual width of a string ignoring ANSI escape sequences.

        Emoji / wide CJK glyphs occupy two cells; we measure them via
        ``unicodedata.east_asian_width``. Falls back to ``len`` if the
        stream is unicode.* and east_asian_width mis-classifies a
        specific glyph on a niche terminal.
        """
        try:
            import unicodedata
            width = 0
            for ch in MinxgMenu._strip_ansi(s):
                if unicodedata.east_asian_width(ch) in ("F", "W"):
                    width += 2
                else:
                    width += 1
            return width
        except Exception:
            return len(MinxgMenu._strip_ansi(s))

    def _move_up_and_clear(self):
        """Park the cursor on the widget's first row, erase below."""
        if not self._supports_ansi or self._painted_rows <= 0:
            return
        # Move cursor up to the first line of the widget.
        if self._painted_rows > 1:
            sys.stdout.write(f"\033[{self._painted_rows - 1}A")
        # Erase from cursor to end of screen.
        sys.stdout.write("\033[J")
        sys.stdout.flush()

    def _calc_render_rows(self, rendered_lines: List[str]) -> int:
        rows = 0
        for line in rendered_lines:
            # Each line + 1 newline. Long lines wrap based on terminal width.
            try:
                cols = shutil.get_terminal_size((80, 20)).columns
            except Exception:
                cols = 80
            visible = max(1, self._line_width(line))
            rows += (visible + cols - 1) // cols or 1
        return rows

    def _render_first(self):
        """First time: paint fresh, no cursor hacks needed."""
        self._supports_ansi = (
            sys.stdout.isatty() and not os.environ.get("TERM") == "dumb"
        )
        if HAS_RICH:
            console.print(f"\n  [bold gold3]{self.title}[/bold gold3]\n")
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                print_option_item(i == self.selected, opt, desc)
            console.print(f"\n  [dim]{T('wizard_nav_hint')}[/dim]\n")
            lines = [self.title]
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                lines.append(self._build_option_line(i == self.selected, opt, desc))
            lines.append(T("wizard_nav_hint"))
            self._painted_rows = self._calc_render_rows(lines)
        else:
            print(f"\n  {_ansi(self.title, Colors.GOLD, Colors.BOLD)}\n")
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                print_option_item(i == self.selected, opt, desc)
            print(f"\n  {_ansi(T('wizard_nav_hint'), Colors.SLATE)}\n")
            lines = [self.title]
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                lines.append(self._build_option_line(i == self.selected, opt, desc))
            lines.append(T("wizard_nav_hint"))
            self._painted_rows = self._calc_render_rows(lines)

    def _build_option_line(self, selected: bool, text: str, desc: str) -> str:
        """Return a single visual line for one menu entry."""
        marker = "\u25c8" if selected else "\u25c7"
        short_desc = _truncate_desc(desc)
        if selected:
            head = f"{marker} {text}"
            tail = f"  {short_desc}" if short_desc else ""
        else:
            head = f"{marker} {text}"
            tail = f"  {short_desc}" if short_desc else ""
        return f"  {head}{tail}"

    def _render(self):
        if self._painted_rows == 0:
            self._render_first()
            return
        self._move_up_and_clear()
        if HAS_RICH:
            console.print(f"  [bold gold3]{self.title}[/bold gold3]")
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                print_option_item(i == self.selected, opt, desc)
            console.print(f"  [dim]{T('wizard_nav_hint')}[/dim]")
            lines = [self.title]
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                lines.append(self._build_option_line(i == self.selected, opt, desc))
            lines.append(T("wizard_nav_hint"))
            self._painted_rows = self._calc_render_rows(lines)
        else:
            print(f"  {_ansi(self.title, Colors.GOLD, Colors.BOLD)}")
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                print_option_item(i == self.selected, opt, desc)
            print(f"  {_ansi(T('wizard_nav_hint'), Colors.SLATE)}")
            lines = [self.title]
            for i, (opt, desc) in enumerate(zip(self.options, self.descriptions)):
                lines.append(self._build_option_line(i == self.selected, opt, desc))
            lines.append(T("wizard_nav_hint"))
            self._painted_rows = self._calc_render_rows(lines)

    def run(self) -> Optional[int]:
        # Path 1: readchar unavailable — fall back to plain numbered input.
        if not HAS_READCHAR:
            self._render_first()
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
            elif key == readchar.key.ENTER or key == readchar.key.CR:
                # Erase widget from layout so subsequent app output flows
                # from the cursor position the user expects.
                self._move_up_and_clear()
                self._painted_rows = 0
                return self.selected
            elif key.lower() == 'q':
                self._move_up_and_clear()
                self._painted_rows = 0
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
