"""
MINXG i18n — English-only internationalization module.

All text is English. The module exists for structural compatibility
with the i18n_data/*.json system (future languages can be added here).

Built-in defaults: a small _DEFAULTS dict ships the most-used keys
inline so a missing i18n_data/{lang}.json file does not turn the
CLI into raw-key soup (e.g. `cmd_minxg` instead of "Start TUI chat").
When i18n_data/en.json is added later, JSON entries override _DEFAULTS.

Public surface:
- LANGUAGES, LANG_NAMES, LANG_CODES
- set_lang / get_lang / get_lang_name / init_i18n
- T(key, lang=None, **kwargs) — translates a key with .format() kwargs
- available_keys(lang=None) -> list[str]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


LANGUAGES = {
    "en": {"name": "English", "native": "English"},
}

LANG_NAMES = ["English"]
LANG_CODES = ["en"]


_current_lang = "en"


_I18N_DIR = Path(__file__).parent / "i18n_data"


_CACHE: Dict[str, Dict[str, str]] = {}


# ==============================================================
# Built-in English defaults — fallback when i18n_data/en.json
# is absent or doesn't cover a key. Add a key here when you find
# a `T("...")` call whose result would otherwise stem from the
# raw key. Keep keys lowercase, ASCII, snake_case, dotted.
# ==============================================================
_DEFAULTS: Dict[str, str] = {
    # Cheatsheet one-liners
    "cmd_minxg":      "Start TUI chat (default)",
    "cmd_docs":       "Open local docs server",
    "cmd_open":       "Start API gateway",
    "cmd_setup":      "Run setup wizard",
    "cmd_model":      "Quick-set model",
    "cmd_api":        "Set API base URL",
    "cmd_key":        "Set API key",
    "cmd_lang":       "Switch language",
    "cmd_config":     "Show current configuration",
    "cmd_status":     "Show runtime status",
    "cmd_tools":      "List available tools",
    "cmd_help":       "Show this help",
    "cmd_gateway":    "Start/stop API gateway",
    "cmd_update":     "Update (removed in this build)",
    "cmd_ext":        "Manage extensions",
    "cmd_skill":      "Manage skills",
    # Cheatsheet structural
    "cheatsheet_title":     "Cheatsheet",
    "cheatsheet_hint":      "Run any of the above to get started.",
    # Steps & inputs
    "step_language":        "Pick your language",
    "wizard_nav_hint":      "Arrow keys to move, Enter to confirm, q to quit",
    "err_number_range":     "Pick a number between {min} and {max}",
    "err_invalid_input":    "Invalid input, try again",
    # Tools
    "tools_title":          "Available toolsets",
    "tools_total":          "Total {total} tools across {sets} toolsets",
    "tools_list_failed":    "Failed to list tools: {error}",
    "status_extensions":    "Tools",
    # Config display
    "cfg_not_set":          "(not set)",
    "cfg_ai_provider":      "AI Provider",
    "cfg_model":            "Model",
    "cfg_api_url":          "API URL",
    "cfg_api_key":          "API Key",
    "cfg_temperature":      "Temperature",
    "cfg_max_tokens":       "Max tokens",
    "cfg_concurrency":      "Concurrency",
    "cfg_max_tool_calls":   "Max tool calls",
    "cfg_gateway_port":     "Gateway port",
    "cfg_gateway_key":      "Gateway auth key",
    "cfg_workers_port":     "Workers port",
    "cfg_logging":          "Logging",
    "cfg_orchestrator":     "Orchestrator",
    "cfg_telemetry":        "Telemetry",
    # Branding & farewell
    "brand_full":           "MINXG — Five-Pillar Worker Platform",
    "brand_short":          "MINXG",
    "goodbye":              "Goodbye.",
    # Extensions
    "ext_list_help":        "List installed extensions",
    "ext_browse_help":      "Browse available extensions",
    "ext_sample_help":      "Install the sample extension",
    "ext_subtitle_load":    "Loaded",
    "ext_subtitle_none":    "No extensions found",
}


def _load_json(lang_code: str) -> Dict[str, str]:
    """Load translations from JSON file (cached)."""
    if lang_code in _CACHE:
        return _CACHE[lang_code]

    filepath = _I18N_DIR / f"{lang_code}.json"
    if filepath.exists():
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _CACHE[lang_code] = data
                return data
        except (json.JSONDecodeError, OSError):
            pass

    # No JSON: cache an empty dict so we don't re-stat the file.
    _CACHE[lang_code] = {}
    return _CACHE[lang_code]


def set_lang(code: str) -> None:
    """Switch current language."""
    global _current_lang
    if code in LANGUAGES:
        _current_lang = code


def get_lang() -> str:
    """Return current language code."""
    return _current_lang


def get_lang_name(code: str) -> str:
    """Return native name of a language."""
    return LANGUAGES.get(code, {}).get("native", code)


def _load_config_lang() -> str:
    """Read language from config.yaml."""
    try:
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            return config.get("lang", "en")
    except Exception:
        pass
    return "en"


def T(key: str, lang: str = None, **kwargs) -> str:
    """Translate a string key.

    Lookup order:
      1. JSON translations for `lang` (i18n_data/{lang}.json) if loaded
      2. Built-in _DEFAULTS dict
      3. The key itself (last-resort fallback for unknown keys)

    Supports .format(**kwargs) for substitution. Missing substitution
    keys fall back to the unformatted text rather than raising.
    """
    if lang is None:
        lang = _current_lang

    translations = _load_json(lang)
    text = translations.get(key)
    if text is None:
        text = _DEFAULTS.get(key)
    if text is None:
        text = key

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def available_keys(lang: str = None) -> list:
    """List all available translation keys for a language.

    Combines JSON entries and _DEFAULTS.
    """
    if lang is None:
        lang = _current_lang
    json_keys = set(_load_json(lang).keys())
    return sorted(json_keys | set(_DEFAULTS.keys()))


def init_i18n() -> None:
    """Initialize i18n from config.yaml."""
    global _current_lang
    _current_lang = _load_config_lang()
    _load_json(_current_lang)



_current_lang = _load_config_lang()
_load_json(_current_lang)
