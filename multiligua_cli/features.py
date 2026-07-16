"""
multiligua_cli/features.py — MINXG Feature Showcase

This module provides a visual showcase of all MINXG features,
designed to be displayed in the TUI and help users discover
what the platform can do.

Features are organized into categories with emoji icons and
short descriptions, making it easy to understand at a glance.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# ═══════════════════════════════════════════════════════════════════
#  Feature Registry
# ═══════════════════════════════════════════════════════════════════

FEATURES: List[Tuple[str, str, str, str]] = [
    # (category, emoji, name, description)

    # ── AI / LLM ──────────────────────────────────────────────────
    ("AI & LLM", "🤖", "Multi-Provider AI", "32+ providers: OpenAI, Anthropic, Google, DeepSeek, xAI, and more"),
    ("AI & LLM", "🧠", "Reasoning Models", "Support for reasoning effort levels (none → xhigh)"),
    ("AI & LLM", "🔄", "Model Switching", "Switch models mid-conversation with /model"),
    ("AI & LLM", "⚡", "Streaming Chat", "Real-time token streaming with typing indicators"),
    ("AI & LLM", "🎯", "Tool Calling", "Function calling with 70+ built-in tools"),
    ("AI & LLM", "🔒", "Safety Guard", "Depth guard + cost guard + anti-loop protection"),

    # ── MCP Integration ───────────────────────────────────────────
    ("MCP", "🔌", "MCP Server", "Expose all workers as MCP tools for Claude Code"),
    ("MCP", "🤝", "Claude Code", "Native integration with Claude Code, Cursor, Windsurf"),
    ("MCP", "🌐", "MCP Clients", "Works with any MCP-compatible client"),

    # ── Workers / Tools ───────────────────────────────────────────
    ("Workers", "📁", "File I/O", "Read, write, search, copy, move files"),
    ("Workers", "🌐", "Network Tools", "HTTP requests, DNS lookup, ping, port scan"),
    ("Workers", "🔐", "Crypto Tools", "Hash, encrypt, decrypt, sign, verify"),
    ("Workers", "🧮", "Math Engine", "300+ mathematical operators across 6 pillars"),
    ("Workers", "📝", "Text Processing", "Format, template, markdown, regex"),
    ("Workers", "📊", "Data Tools", "CSV, JSON, encoding, compression"),
    ("Workers", "💻", "System Tools", "Process management, shell exec, platform detection"),
    ("Workers", "🤖", "AI Tools", "LLM integration, RAG, embeddings"),

    # ── Polyglot Bridges ──────────────────────────────────────────
    ("Polyglot", "🔗", "C/C++ Bridge", "Native C/C++ operators via FFI"),
    ("Polyglot", "🦞", "Go Bridge", "Go-based core with JSON-RPC protocol"),
    ("Polyglot", "☕", "Java Bridge", "JVM daemon with vector engine"),
    ("Polyglot", "🦀", "Rust Bridge", "Memory-safe operators via cffi"),
    ("Polyglot", "📐", "R Scripts", "Statistical computing integration"),
    ("Polyglot", "🔭", "Julia Bridge", "High-performance numerical computing"),
    ("Polyglot", "🌐", "WASM Bridge", "WebAssembly sandbox execution"),

    # ── Platform Support ──────────────────────────────────────────
    ("Platform", "📱", "Android (Termux)", "Full support on Android via Termux"),
    ("Platform", "🪟", "Windows", "Native Windows support"),
    ("Platform", "🐧", "Linux", "Full Linux support"),
    ("Platform", "🍎", "macOS", "macOS compatible"),
    ("Platform", "🔄", "WSL", "Windows Subsystem for Linux"),

    # ── i18n ──────────────────────────────────────────────────────
    ("i18n", "🌍", "12 Languages", "English, 中文, 日本語, 한국어, Français, Deutsch, Español, Português, Русский, العربية, हिन्दी, ไทย"),
    ("i18n", "🔄", "Live Switch", "Switch language instantly with /lang"),

    # ── Advanced Features ─────────────────────────────────────────
    ("Advanced", "🚀", "Driver Engine", "RK4/RK45 integration with chaos detection"),
    ("Advanced", "🧬", "Self-Evolution", "Built-in learning engine that improves over time"),
    ("Advanced", "🔍", "Reverse Studio", "Deobfuscation and reverse engineering tools"),
    ("Advanced", "📈", "Benchmark Tools", "Performance benchmarking and profiling"),
    ("Advanced", "🎨", "Theme System", "Customizable TUI themes"),
    ("Advanced", "⌨️", "Keyboard Shortcuts", "Vim-style and Emacs-style keybindings"),
    ("Advanced", "💾", "Persistence", "Session memory and conversation history"),
    ("Advanced", "🔔", "Notifications", "Desktop and mobile notifications"),
    ("Advanced", "🌐", "API Gateway", "OpenAI-compatible /v1 API server"),
    ("Advanced", "📡", "Multi-Channel", "Telegram, Discord, Slack integration"),

    # ── DevTools ──────────────────────────────────────────────────
    ("DevTools", "🔨", "Android Forge", "APK building and Android development"),
    ("DevTools", "⚙️", "Dev Forge", "Quad-forge development workflow"),
    ("DevTools", "🐚", "Dev Shell", "Interactive development environment"),
    ("DevTools", "🔍", "Audit Worker", "Code auditing and security scanning"),
]

# Category order for display
CATEGORY_ORDER = [
    "AI & LLM",
    "MCP",
    "Workers",
    "Polyglot",
    "Platform",
    "i18n",
    "Advanced",
    "DevTools",
]


def get_features_by_category() -> Dict[str, List[Tuple[str, str, str]]]:
    """Group features by category, preserving order."""
    result: Dict[str, List[Tuple[str, str, str]]] = {}
    for cat, emoji, name, desc in FEATURES:
        if cat not in result:
            result[cat] = []
        result[cat].append((emoji, name, desc))
    return result


def print_features_table(console=None) -> None:
    """Print a formatted feature table."""
    if console is None:
        from multiligua_cli.utils import console
    else:
        from multiligua_cli.utils import console

    try:
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
    except ImportError:
        # Fallback to plain text
        for cat in CATEGORY_ORDER:
            cat_features = [(e, n, d) for c, e, n, d in FEATURES if c == cat]
            if not cat_features:
                continue
            print(f"\n{'─' * 60}")
            print(f"  {cat}")
            print(f"{'─' * 60}")
            for emoji, name, desc in cat_features:
                print(f"  {emoji}  {name:25}  {desc}")
        return

    by_category = get_features_by_category()

    for cat in CATEGORY_ORDER:
        features = by_category.get(cat, [])
        if not features:
            continue

        table = Table(
            show_header=False,
            show_edge=False,
            padding=(0, 1),
            box=box.SIMPLE,
            expand=True,
        )
        table.add_column("Emoji", style="bold", width=3)
        table.add_column("Feature", style="bold cyan", width=25)
        table.add_column("Description", style="dim")

        for emoji, name, desc in features:
            table.add_row(emoji, name, desc)

        console.print(Panel(
            table,
            title=f"[bold gold3]{cat}[/bold gold3]",
            border_style="bright_blue",
            padding=(0, 1),
        ))


def get_feature_count() -> int:
    """Return total number of features."""
    return len(FEATURES)


def get_category_count() -> int:
    """Return number of categories."""
    return len(CATEGORY_ORDER)


# ═══════════════════════════════════════════════════════════════════
#  Selling Points (for README, marketing, etc.)
# ═══════════════════════════════════════════════════════════════════

SELLING_POINTS = [
    {
        "icon": "🔌",
        "title": "MCP Server Integration",
        "desc": "Expose 70+ workers as MCP tools — works with Claude Code, Cursor, Windsurf, and any MCP client.",
    },
    {
        "icon": "🤖",
        "title": "32+ AI Providers",
        "desc": "OpenAI, Anthropic, Google, DeepSeek, xAI, and more. Switch models mid-conversation.",
    },
    {
        "icon": "🧮",
        "title": "300+ Math Operators",
        "desc": "Geometric Algebra, Category Theory, Information Geometry, Topology, Chaos, Fiber Bundles, SymbDiff.",
    },
    {
        "icon": "🔗",
        "title": "Polyglot Bridges",
        "desc": "C/C++, Go, Java, Rust, R, Julia, WASM — call native code from Python seamlessly.",
    },
    {
        "icon": "🌍",
        "title": "12 Languages",
        "desc": "English, 中文, 日本語, 한국어, Français, Deutsch, Español, Português, Русский, العربية, हिन्दी, ไทย.",
    },
    {
        "icon": "📱",
        "title": "Android + Windows",
        "desc": "Full support on Termux (Android) and Windows. One package, all platforms.",
    },
    {
        "icon": "🚀",
        "title": "Driver Engine",
        "desc": "RK4/RK45 integration with chaos detection, Lyapunov exponent tracking, singularity awareness.",
    },
    {
        "icon": "🧬",
        "title": "Self-Evolution",
        "desc": "Built-in learning engine that records patterns and improves over time.",
    },
    {
        "icon": "🔐",
        "title": "Safety Guards",
        "desc": "Depth guard, cost guard, anti-loop protection — production-ready safety.",
    },
    {
        "icon": "🌐",
        "title": "API Gateway",
        "desc": "OpenAI-compatible /v1 API server. Drop-in replacement for OpenAI SDK.",
    },
]


def print_selling_points(console=None) -> None:
    """Print selling points in a formatted way."""
    if console is None:
        from multiligua_cli.utils import console

    try:
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
    except ImportError:
        for sp in SELLING_POINTS:
            print(f"\n{sp['icon']}  {sp['title']}")
            print(f"    {sp['desc']}")
        return

    table = Table(
        show_header=False,
        show_edge=False,
        padding=(0, 1),
        box=box.SIMPLE,
    )
    table.add_column("Icon", style="bold", width=3)
    table.add_column("Title", style="bold cyan", width=25)
    table.add_column("Description", style="dim")

    for sp in SELLING_POINTS:
        table.add_row(sp["icon"], sp["title"], sp["desc"])

    console.print(Panel(
        table,
        title="[bold gold3]◆  Why MINXG?[/bold gold3]",
        border_style="bright_blue",
        padding=(1, 2),
    ))
