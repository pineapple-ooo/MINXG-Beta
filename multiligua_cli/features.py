"""
multiligua_cli/features.py — MINXG Feature Showcase + EXPERIMENTAL extras

Two things live in this module:

1. The **stable** feature showcase (``FEATURES``, ``print_features``,
   ``SELLING_POINTS``, ...) — used by ``minxg features`` and the TUI to
   help users discover what the platform can do. Safe to call anytime.

2. An **EXPERIMENTAL** secondary surface that is *not* wired into the
   shipped CLI (no command, no TUI menu, no wizard reach) — kept here so
   the design ideas are recoverable before we know whether they earn a
   real home. Everything in this half may print/log a warning at runtime
   ("EXPERIMENTAL ...") and its signature may change without notice:
     - Spinner, context_usage_bar     (rich-free terminal helpers)
     - export_to_markdown             (chat -> markdown dump)
     - share_to_gist                  (prints the `gh` command to run)
     - play_notification              (BEL char — disabled by default)
     - welcome_animation              (not wired)
     - SessionManager, QuickFeedback  (no driver interface yet)
     - SilentFeatures                 (singleton: get_silent())
           auto_save / gc_sessions / disk_usage_report / rotate_logs
           keepalive_check / optimize_memory_index / silent_error_log
           collect_metrics / check_updates(*stub*) / dependency_health

The stable TUI is in ``multiligua_cli.tui_chat``.
"""
from __future__ import annotations

import os
import sys
import time
import json as _json
import threading
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable

log = logging.getLogger("features")

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


def print_features(console=None) -> None:
    """Alias for :func:`print_features_table` — the name `minxg features` expects."""
    print_features_table(console=console)


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


# ═══════════════════════════════════════════════════════════════════
#  EXPERIMENTAL surface — not wired into the shipped CLI.
#  See the module docstring for the full list + disclaimer.
# ═══════════════════════════════════════════════════════════════════

_EXPERIMENTAL_FEATURE_NAMES = frozenset({
    "Spinner", "context_usage_bar", "export_to_markdown",
    "share_to_gist", "play_notification", "welcome_animation",
    "SessionManager", "QuickFeedback", "SilentFeatures", "get_silent",
    "role_color",
})


def _warn_experimental(name: str) -> None:
    """Log a one-line warning when an experimental feature is invoked."""
    log.warning("EXPERIMENTAL feature %s is not part of the stable CLI surface", name)


def role_color(role: str) -> str:
    """Best-effort ANSI color for a chat role, for the (unwired) experimental TUI bits."""
    return {
        "user": "\033[38;5;75m",
        "assistant": "\033[38;5;113m",
        "tool": "\033[38;5;180m",
        "system": "\033[38;5;244m",
    }.get(role, "\033[0m")


class Spinner:
    """Minimal rich-free terminal spinner. EXPERIMENTAL — not wired into the TUI."""

    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, text: str = ""):
        self.text = text
        self._idx = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, text: str = None):
        if text:
            self.text = text
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        while self._running:
            sys.stdout.write(f"\r\033[K{self._frames[self._idx % len(self._frames)]} {self.text}")
            sys.stdout.flush()
            self._idx += 1
            time.sleep(0.1)

    def stop(self, result: str = "✓"):
        self._running = False
        if self._thread:
            self._thread.join(0.3)
        sys.stdout.write(f"\r\033[K{result}\n")


def context_usage_bar(used_tokens: int, max_tokens: int, width: int = 40) -> str:
    """Render a colored ASCII progress bar for context-window usage. EXPERIMENTAL."""
    pct = min(used_tokens / max_tokens, 1.0) if max_tokens else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    color = "\033[32m" if pct < 0.5 else ("\033[33m" if pct < 0.8 else "\033[31m")
    return f"{color}[{bar}]\033[0m {pct*100:.0f}% ({used_tokens}/{max_tokens})"


def suggest_command(wrong: str) -> Optional[str]:
    """Fuzzy-match an unknown CLI verb against the known command list. EXPERIMENTAL."""
    from difflib import get_close_matches
    commands = ["setup", "model", "api", "key", "lang", "config", "status",
                "tools", "gateway", "update", "ext", "help", "docs", "open",
                "skill", "list", "browse", "sample"]
    matches = get_close_matches(wrong, commands, n=2, cutoff=0.5)
    return matches[0] if matches else None


def export_to_markdown(messages: List[Dict], output: str = None) -> str:
    """Dump a chat transcript to a markdown file and return its path. EXPERIMENTAL."""
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = output or f"minxg_conversation_{ts}.md"
    lines = [f"# MINXG Conversation — {ts}", ""]
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"### {role.upper()}")
        lines.append("")
        lines.append(content)
        lines.append("")
        if "tool_calls" in msg:
            for tc in msg.get("tool_calls", []):
                lines.append(
                    f"> 🔧 {tc.get('name', 'tool')}: "
                    f"`{_json.dumps(tc.get('params', {}), ensure_ascii=False)[:200]}`"
                )
                lines.append("")
    text = "\n".join(lines)
    Path(output).write_text(text, encoding="utf-8")
    return output


def share_to_gist(file_path: str, description: str = "MINXG conversation") -> str:
    """Return (does not run) the `gh gist create` command to share a file. EXPERIMENTAL."""
    return f'gh gist create {file_path} -d "{description}" --public'


def play_notification(text: str = ""):
    """Emit a terminal bell. EXPERIMENTAL — disabled by default in the stable CLI."""
    sys.stdout.write("\a")
    sys.stdout.flush()


def welcome_animation():
    """Print a short animated banner. EXPERIMENTAL — not wired into the TUI."""
    frames = [
        "\033[38;5;75m⚡ MINXG\033[0m",
        "\033[38;5;113m⚡ MINXG ·\033[0m",
        "\033[38;5;213m⚡ MINXG ··\033[0m",
        "\033[38;5;82m⚡ MINXG ···\033[0m",
    ]
    for frame in frames:
        sys.stdout.write(f"\r\033[K{frame}")
        sys.stdout.flush()
        time.sleep(0.08)
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


class SessionManager:
    """Save/load/list chat sessions under ~/.minxg/sessions. EXPERIMENTAL."""

    def __init__(self, sessions_dir: str = None):
        self.sessions_dir = Path(sessions_dir or os.path.expanduser("~/.minxg/sessions"))
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, messages: List[Dict]):
        path = self.sessions_dir / f"{session_id}.json"
        path.write_text(_json.dumps(messages, ensure_ascii=False, indent=2))

    def load(self, session_id: str) -> Optional[List[Dict]]:
        path = self.sessions_dir / f"{session_id}.json"
        if path.exists():
            return _json.loads(path.read_text())
        return None

    def list_sessions(self) -> List[Dict]:
        sessions = []
        for f in sorted(self.sessions_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            sessions.append({
                "id": f.stem, "mtime": f.stat().st_mtime,
                "size": f.stat().st_size,
            })
        return sessions[:20]

    def cleanup(self, max_age_days: int = 30):
        cutoff = time.time() - max_age_days * 86400
        for f in self.sessions_dir.glob("*.json"):
            if f.stat().st_mtime < cutoff:
                f.unlink()


class QuickFeedback:
    """Append-only local feedback log at ~/.minxg/feedback.jsonl. EXPERIMENTAL."""

    def __init__(self, feedback_file: str = None):
        self.feedback_file = Path(feedback_file or os.path.expanduser("~/.minxg/feedback.jsonl"))
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)

    def record(self, rating: str, comment: str = "", context: dict = None):
        entry = {
            "timestamp": time.time(),
            "rating": rating,
            "comment": comment,
            "context": context or {},
        }
        with self.feedback_file.open("a") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")


class SilentFeatures:
    """[EXPERIMENTAL] Background metrics & self-care surface.

    *Not* surfaced by the stable CLI. Methods may change, may no-op,
    or may be removed without notice. Call only if you read the source.
    """

    def __init__(self):
        _warn_experimental("SilentFeatures.__init__")
        self._start_time = time.time()
        self._stats = {
            "commands_run": 0, "tools_called": 0, "total_tokens": 0,
            "errors": 0, "sessions": 0, "uptime_start": self._start_time,
        }
        self._experimental_warned = set()  # warn-once per method name

    def _warn_method(self, name: str) -> None:
        if name not in self._experimental_warned:
            _warn_experimental(f"SilentFeatures.{name}")
            self._experimental_warned.add(name)

    def auto_save(self, session_id: str, messages: List[Dict]):
        """[EXPERIMENTAL] save a chat session to ~/.minxg/sessions."""
        self._warn_method("auto_save")
        mgr = SessionManager()
        mgr.save(session_id, messages)

    def gc_sessions(self):
        """[EXPERIMENTAL] remove sessions older than 30 days."""
        self._warn_method("gc_sessions")
        mgr = SessionManager()
        mgr.cleanup()

    def disk_usage_report(self, data_dir: Optional[str] = None) -> dict:
        """[EXPERIMENTAL] report total disk usage under `data_dir`."""
        self._warn_method("disk_usage_report")
        d = Path(data_dir or os.path.expanduser("~/.minxg"))
        total = 0
        try:
            for f in d.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except Exception:
            pass
        return {"dir": str(d), "total_bytes": total, "mb": round(total / (1024 * 1024), 2)}

    def rotate_logs(self, log_dir: Optional[str] = None, max_files: int = 10):
        """[EXPERIMENTAL] keep only the latest `max_files` log files."""
        self._warn_method("rotate_logs")
        ld = Path(log_dir or os.path.expanduser("~/.minxg/logs"))
        for pat in ("*.log", "*.log.*"):
            files = sorted(ld.glob(pat), key=lambda x: x.stat().st_mtime)
            while len(files) > max_files:
                files.pop(0).unlink()

    def keepalive_check(
        self, url: str = "https://api.openai.com/v1/models", timeout: int = 3
    ) -> bool:
        """[EXPERIMENTAL] probe `url` to see if the AI provider is reachable.

        Returns True on 2xx, False otherwise. Does **not** authenticate
        — only checks that the endpoint is up.
        """
        self._warn_method("keepalive_check")
        import urllib.request
        try:
            req = urllib.request.Request(url)
            urllib.request.urlopen(req, timeout=timeout)
            return True
        except Exception:
            return False

    def optimize_memory_index(self):
        """[EXPERIMENTAL] run `PRAGMA optimize` on ~/.minxg/memory.db if present."""
        self._warn_method("optimize_memory_index")
        try:
            import sqlite3
            db = Path(os.path.expanduser("~/.minxg/memory.db"))
            if db.exists():
                conn = sqlite3.connect(str(db))
                conn.execute("PRAGMA optimize")
                conn.close()
        except Exception:
            pass

    def silent_error_log(self, error: Exception, context: str = ""):
        """[EXPERIMENTAL] log an error to the features log channel only."""
        self._warn_method("silent_error_log")
        log.error("[SILENT] %s: %s", context, error)

    def collect_metrics(self, metric: str, value: float):
        """[EXPERIMENTAL] increment an in-memory counter `metric` by `value`."""
        self._warn_method("collect_metrics")
        self._stats[metric] = self._stats.get(metric, 0) + value

    def check_updates(self, repo_url: str = "https://github.com/minxg/minxg"):
        """[EXPERIMENTAL] STUB. Always returns None until the check
        backend is implemented; callers must not rely on a version bump
        prompt from this entry point in this release."""
        self._warn_method("check_updates")
        return None

    def dependency_health(self) -> Dict[str, bool]:
        """[EXPERIMENTAL] ad-hoc import probe of common deps. Diagnostic only."""
        self._warn_method("dependency_health")
        checks: Dict[str, bool] = {}
        for mod in ["rich", "prompt_toolkit", "jinja2", "PIL", "yaml", "sqlite3"]:
            try:
                __import__(mod)
                checks[mod] = True
            except ImportError:
                checks[mod] = False
        return checks


_silent: Optional[SilentFeatures] = None


def get_silent() -> SilentFeatures:
    """[EXPERIMENTAL] return the process-wide SilentFeatures singleton."""
    _warn_experimental("get_silent")
    global _silent
    if _silent is None:
        _silent = SilentFeatures()
    return _silent


def list_experimental_exports():
    """Return a sorted list of every EXPERIMENTAL symbol in this module."""
    return sorted(_EXPERIMENTAL_FEATURE_NAMES)
