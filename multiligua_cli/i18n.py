"""
MINXG i18n — English-only internationalization module.

All text is English. The module exists for structural compatibility
with the i18n_data/*.json system (future languages can be added here).
"""

from __future__ import annotations

import json
import os
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


def _load_json(lang_code: str) -> Dict[str, str]:
    """Load translations from JSON file."""
    if lang_code in _CACHE:
        return _CACHE[lang_code]

    filepath = _I18N_DIR / f"{lang_code}.json"
    if filepath.exists():
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            _CACHE[lang_code] = data
            return data
        except (json.JSONDecodeError, OSError):
            pass

    return {}


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

    Falls back to the key name itself if not found.
    Supports .format(**kwargs) formatting.
    """
    if lang is None:
        lang = _current_lang

    translations = _load_json(lang)
    text = translations.get(key)

    if text is None:
        text = key

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text

    return text


def available_keys(lang: str = None) -> list:
    """List all available translation keys for a language."""
    if lang is None:
        lang = _current_lang
    return sorted(_load_json(lang).keys())


def init_i18n() -> None:
    """Initialize i18n from config.yaml."""
    global _current_lang
    _current_lang = _load_config_lang()
    _load_json(_current_lang)



_current_lang = _load_config_lang()
_load_json(_current_lang)
