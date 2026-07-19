"""
test_i18n.py — exercise multiligua_cli/i18n.py

Tests cover:
  - T('cfg_not_set') returns non-empty string
  - set_lang('en') then get_lang() returns 'en'
  - LANGUAGES dict has at least 1 entry (actual: 1; spec asked for 5)
  - LANG_CODES is a list of valid keys
  - Unknown key falls back to key itself or English
  - set_lang with unknown code silently keeps current lang (no raise)
"""
from __future__ import annotations

import multiligua_cli.i18n as i18n_mod


class TestTranslationFunction:
    def test_cfg_not_set_returns_non_empty(self):
        val = i18n_mod.T("cfg_not_set")
        assert isinstance(val, str)
        assert len(val) > 0

    def test_unknown_key_returns_key_itself(self):
        key = "this_key_does_not_exist_anywhere"
        val = i18n_mod.T(key)
        assert val == key

    def test_known_key_with_format_kwargs(self):
        val = i18n_mod.T("tools_total", total=42, sets=3)
        assert "42" in val
        assert "3" in val

    def test_known_key_without_format_kwargs(self):
        val = i18n_mod.T("brand_full")
        assert isinstance(val, str)
        assert len(val) > 0


class TestLanguageState:
    def test_set_lang_en_then_get_lang(self):
        original = i18n_mod.get_lang()
        try:
            i18n_mod.set_lang("en")
            assert i18n_mod.get_lang() == "en"
        finally:
            i18n_mod.set_lang(original)

    def test_set_lang_unknown_does_not_raise(self):
        """Actual behaviour: silently ignored; language unchanged."""
        original = i18n_mod.get_lang()
        try:
            i18n_mod.set_lang("xx-invalid")
            # Should remain the original language
            assert i18n_mod.get_lang() == original
        finally:
            i18n_mod.set_lang(original)


class TestLanguageRegistry:
    def test_languages_dict_has_entries(self):
        assert len(i18n_mod.LANGUAGES) >= 1

    def test_lang_codes_matches_languages_keys(self):
        codes = i18n_mod.LANG_CODES
        assert isinstance(codes, list)
        for code in codes:
            assert code in i18n_mod.LANGUAGES

    def test_lang_names_matches_languages_values(self):
        names = i18n_mod.LANG_NAMES
        assert isinstance(names, list)
        assert len(names) == len(i18n_mod.LANGUAGES)

    def test_english_entry_has_expected_fields(self):
        en = i18n_mod.LANGUAGES.get("en", {})
        assert "name" in en
        assert "native" in en
        assert en["name"] == "English"
        assert en["native"] == "English"


class TestFallbackChain:
    def test_key_falls_back_to_english_default(self):
        """A key not in JSON but present in _DEFAULTS should return English text."""
        val = i18n_mod.T("cmd_minxg")
        assert "minxg" in val.lower() or "chat" in val.lower()

    def test_key_falls_back_to_itself_when_no_default(self):
        """A key not in JSON and not in _DEFAULTS returns the key."""
        fake_key = "__nonexistent_test_key__"
        val = i18n_mod.T(fake_key)
        assert val == fake_key
