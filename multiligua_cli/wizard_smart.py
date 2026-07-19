"""multiligua_cli/wizard_smart.py — context-aware setup wizard (v0.16.5).

The original ``multiligua_cli/wizard_ui.py`` is large but not smart — it
asks the same questions regardless of what the AI/runner actually needs.
This module adds four contributions:

* ``smart_suggest(schema)`` — given what's missing in the user's config,
  returns the next best question (issue-driven).
* ``skill_discover()`` — walks ``~/.hermes/skills/`` and ``/skills/``
  mounted in this repo, exposing each skill as a hint to the AI.
* ``progress_label(step, total)`` — pretty progress bar for ``wizard``.
* ``default_for(question, ctx)`` — context-aware default for the next
  prompt (e.g. multi-line OS detection, no need to ask if Termux).

Pure stdlib, no UI lib — the wizard renders to a dict; the existing
``wizard_ui`` consumes these to actually draw.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_NAMES = (
    ("provider", "Which LLM provider are we using?"),
    ("model", "Default model name?"),
    ("api_key", "API key (or 0 to skip)?"),
    ("base_url", "API base URL?"),
    ("language", "Default UI language (en/zh/ja/...)?")
)


def schema() -> List[Tuple[str, str]]:
    return list(_NAMES)


def smart_suggest(cfg: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    """Return (key, question, suggested_value) for the next missing field,
    or None when all required keys are present.

    Strategy:
      1. walk schema in order.
      2. if a value is missing or empty, ask the question.
      3. for known fields, propose a smart default.
    """
    cfg = cfg or {}
    for key, q in _NAMES:
        v = cfg.get(key)
        if v is not None and str(v).strip() != "":
            continue
        default = default_for(key, cfg)
        return (key, q, default)
    return None


def default_for(key: str, ctx: Optional[Dict[str, Any]] = None) -> str:
    """Return a context-aware default value for the key."""
    ctx = ctx or {}
    if key == "provider":
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "openai"
    if key == "model":
        return "gpt-4o-mini"
    if key == "api_key":
        return os.environ.get("OPENAI_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if key == "base_url":
        provider = (ctx.get("provider") or "").lower()
        if provider == "anthropic":
            return "https://api.anthropic.com/v1"
        return "https://api.openai.com/v1"
    if key == "language":
        sys_lang = platform.system()
        try:
            env_lang = os.environ.get("LANG", "").lower()
            if env_lang.startswith("zh"):
                return "zh"
            if env_lang.startswith("ja"):
                return "ja"
            if env_lang.startswith("ko"):
                return "ko"
            if env_lang.startswith("es"):
                return "es"
            if env_lang.startswith("fr"):
                return "fr"
            if env_lang.startswith("pt"):
                return "pt-BR"
        except Exception:
            pass
        return "en"
    return ""


def skill_discover() -> List[Dict[str, str]]:
    """Probe the user's home + this repo's `skills/` for available skills.

    Returns a list of {name, path, kind} entries — the AI uses these to
    prime the prompt.
    """
    out: List[Dict[str, str]] = []
    home = Path.home()
    for root in (home / ".hermes" / "skills",
                  Path(__file__).resolve().parent.parent / ".hermes" / "skills"):
        if not root.exists():
            continue
        for p in root.rglob("SKILL.md"):
            out.append({
                "name": p.parent.name,
                "path": str(p),
                "kind": "hermes-skill",
            })
    return out


def progress_label(step: int, total: int, label: str = "Setup") -> str:
    """Return a single-line progress string (label + bar + %%)."""
    pct = max(0.0, min(1.0, step / total if total > 0 else 0))
    bar_w = 24
    fill = int(bar_w * pct)
    bar = "=" * fill + "-" * (bar_w - fill)
    return f"{label} |{bar}| {int(pct * 100)}% ({step}/{total})"


def next_step_summary(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Return a renderable summary of where the wizard is at."""
    needed = sum(1 for k, _ in _NAMES if not cfg.get(k))
    return {
        "config": cfg,
        "needed": needed,
        "schema": [{"key": k, "question": q} for k, q in _NAMES],
        "tools_check": {
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "git": shutil.which("git") is not None,
            "buildozer": shutil.which("buildozer") is not None,
            "rustc": shutil.which("rustc") is not None,
        },
        "platform": {
            "system": platform.system(),
            "python": platform.python_version(),
            "tty": sys_stdin_is_tty(),
        },
        "skills_available": [s["name"] for s in skill_discover()],
    }


def sys_stdin_is_tty() -> bool:
    try:
        import sys as _s
        return _s.stdin.isatty()
    except Exception:
        return False