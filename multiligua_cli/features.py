"""
multiligua_cli/features.py — secondary feature surface.

This module is **experimental**. Nothing in here is wired into the
shipped CLI surface (no command, no TUI menu, no wizard reach) —
it exists so the design ideas are recoverable before we know whether
they earn a real home.

Experimental surface (call at your own risk):
  - Spinner, context_usage_bar     (rich-free terminal helpers)
  - export_to_markdown             (chat → markdown dump)
  - share_to_gist                  (prints the `gh` command to run)
  - play_notification              (BEL char — disabled by default)
  - THEMES, SHORTCUTS              (placeholders, not surfaced)
  - welcome_animation              (not wired)
  - SessionManager, QuickFeedback  (no driver interface yet)
  - SilentFeatures                 (singleton: get_silent())
        auto_save / gc_sessions / disk_usage_report / rotate_logs
        keepalive_check / optimize_memory_index / silent_error_log
        collect_metrics / check_updates(*None*) / dependency_health

Anything you call from this module may print warnings at runtime
("EXPERIMENTAL …"). The stable TUI is in `multiligua_cli.tui_chat`.
"""
from __future__ import annotations
import os
import sys
import time
import json as _json
import threading
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable

log = logging.getLogger("features")


_EXPERIMENTAL_FEATURE_NAMES = frozenset({
    "Spinner", "context_usage_bar", "export_to_markdown",
    "share_to_gist", "play_notification", "THEMES", "SHORTCUTS",
    "welcome_animation", "SessionManager", "QuickFeedback",
    "SilentFeatures", "get_silent", "role_color",
})


def _warn_experimental(name: str) -> None:
    """Log a one-line warning when an experimental feature is invoked."""
    log.warning("EXPERIMENTAL feature %s is not part of the stable CLI surface", name)
def role_color(role: str) -> str:
    return {
    }.get(role, "\033[0m")

class Spinner:
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    def __init__(self, text: str = ""):
        self.text = text
        self._idx = 0
        self._running = False
        self._thread = None

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
    pct = min(used_tokens / max_tokens, 1.0) if max_tokens else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    color = "\033[32m" if pct < 0.5 else ("\033[33m" if pct < 0.8 else "\033[31m")
    return f"{color}[{bar}]\033[0m {pct*100:.0f}% ({used_tokens}/{max_tokens})"

def suggest_command(wrong: str) -> Optional[str]:
    from difflib import get_close_matches
    commands = ["setup", "model", "api", "key", "lang", "config", "status",
                "tools", "gateway", "update", "ext", "help", "docs", "open",
                "skill", "list", "browse", "sample"]
    matches = get_close_matches(wrong, commands, n=2, cutoff=0.5)
    return matches[0] if matches else None

def export_to_markdown(messages: List[Dict], output: str = None) -> str:
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
                lines.append(f"> 🔧 {tc.get('name', 'tool')}: `{_json.dumps(tc.get('params', {}), ensure_ascii=False)[:200]}`")
                lines.append("")
    text = "\n".join(lines)
    Path(output).write_text(text, encoding="utf-8")
    return output

def share_to_gist(file_path: str, description: str = "MINXG conversation") -> str:
    return f"gh gist create {file_path} -d \"{description}\" --public"

def play_notification(text: str = ""):
    sys.stdout.write("\a")
    sys.stdout.flush()

THEMES = {
    "dark": {"bg": "", "primary": "\033[38;5;75m", "secondary": "\033[38;5;180m", "reset": "\033[0m"},
    "light": {"bg": "", "primary": "\033[38;5;25m", "secondary": "\033[38;5;94m", "reset": "\033[0m"},
    "colorful": {"bg": "", "primary": "\033[38;5;213m", "secondary": "\033[38;5;82m", "reset": "\033[0m"},
    "minimal": {"bg": "", "primary": "\033[0m", "secondary": "\033[0m", "reset": "\033[0m"},
}

SHORTCUTS = {
}

def welcome_animation():
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
        return {"dir": str(d), "total_bytes": total, "mb": round(total / (1024*1024), 2)}

    def rotate_logs(self, log_dir: Optional[str] = None, max_files: int = 10):
        """[EXPERIMENTAL] keep only the latest `max_files` log files."""
        self._warn_method("rotate_logs")
        import glob
        patterns = ["*.log", "*.log.*"]
        ld = Path(log_dir or os.path.expanduser("~/.minxg/logs"))
        for pat in patterns:
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
