"""
test_cli_tui.py — exercise multiligua_cli/tui_chat.py, interactive.py, utils.py

Tests cover:
  - print_banner does not raise (capture stdout)
  - HAS_RICH fallback path renders plain text
  - colorize escapes [ ] when HAS_RICH=True to avoid MarkupError
  - _escape_markup handles brackets, backslashes, unicode
  - ensure_config decorator: missing config calls setup then continues
  - _save_config writes valid YAML to given path
  - get_config_path returns existing file or default path
"""
from __future__ import annotations

import os
import sys
import yaml
from pathlib import Path
from unittest import mock
import pytest

import multiligua_cli.utils as utils_mod
import multiligua_cli.tui_chat as tui_mod
import multiligua_cli.wizard_ui as wizard_mod
import multiligua_cli.interactive as interactive_mod


# ── print_banner ────────────────────────────────────────────────────────────

class TestPrintBanner:
    def test_banner_does_not_raise(self, capsys):
        """print_banner from utils should complete without exception."""
        utils_mod.print_banner()
        captured = capsys.readouterr()
        # Banner should produce some output
        assert captured.out or captured.err

    def test_tui_chat_banner_does_not_raise(self, capsys):
        """tui_chat.print_banner delegates to wizard_ui banner — should not raise."""
        with mock.patch.object(tui_mod, "_wizard_chat_banner"):
            tui_mod.print_banner()
        captured = capsys.readouterr()
        assert captured.out != "" or captured.err != ""


# ── HAS_RICH fallback path ──────────────────────────────────────────────────

class TestHasRichFallback:
    def test_colorize_no_rich_returns_ansi_wrapped(self, monkeypatch, capsys):
        """When HAS_RICH=False, colorize should wrap text with ANSI codes."""
        monkeypatch.setattr(utils_mod, "HAS_RICH", False)
        result = utils_mod.colorize("hello", utils_mod.Colors.RED)
        assert utils_mod.Colors.RED in result
        assert "hello" in result
        assert utils_mod.Colors.RESET in result

    def test_banner_no_rich_produces_plain_text(self, monkeypatch, capsys):
        monkeypatch.setattr(utils_mod, "HAS_RICH", False)
        utils_mod.print_banner()
        captured = capsys.readouterr()
        assert "MINXG" in captured.out

    def test_wizard_banner_no_rich_produces_ansi(self, monkeypatch, capsys):
        monkeypatch.setattr(wizard_mod, "HAS_RICH", False)
        wizard_mod.print_banner()
        captured = capsys.readouterr()
        assert "MINXG" in captured.out
        # Should contain ANSI escape sequences when not HAS_RICH
        assert "\033[" in captured.out


# ── _escape_markup ──────────────────────────────────────────────────────────

class TestEscapeMarkup:
    def test_escapes_square_brackets(self):
        raw = "some [bracketed] text"
        out = utils_mod._escape_markup(raw)
        # Brackets should be prefixed with backslash so Rich doesn't see markup
        assert "\\[" in out
        assert "\\]" in out

    def test_escapes_backslashes(self):
        raw = "path\\to\\[file]"
        out = utils_mod._escape_markup(raw)
        # Backslashes preserved; brackets escaped
        assert "\\\\[" in out or "\\[" in out
        assert "to" in out

    def test_escapes_unicode(self):
        raw = "日本語 [test]"
        out = utils_mod._escape_markup(raw)
        assert "日本語" in out
        assert "test" in out
        assert "\\[" in out

    def test_plain_text_unchanged_except_brackets(self):
        raw = "hello world"
        out = utils_mod._escape_markup(raw)
        assert out == "hello world"

    def test_multiple_bracket_pairs(self):
        raw = "[a][b][c]"
        out = utils_mod._escape_markup(raw)
        assert out.count("\\[") == 3
        assert out.count("\\]") == 3


# ── ensure_config decorator ─────────────────────────────────────────────────

class TestEnsureConfig:
    def test_missing_config_calls_setup_then_continues(self, tmp_path, monkeypatch):
        """When config.yaml is missing, decorator runs setup then calls func."""
        call_log = []

        @utils_mod.ensure_config
        def my_func():
            call_log.append("func")
            return 42

        cfg_path = tmp_path / "config.yaml"
        # Ensure config does NOT exist
        assert not cfg_path.exists()

        with mock.patch.object(utils_mod, "get_config_path", return_value=cfg_path):
            with mock.patch(
                "multiligua_cli.setup.run_setup", return_value=0
            ) as setup_mock:
                rc = my_func()

        assert rc == 42
        assert call_log == ["func"]
        setup_mock.assert_called_once()

    def test_existing_config_skips_setup(self, tmp_path):
        """When config.yaml exists, decorator does NOT run setup."""
        call_log = []

        @utils_mod.ensure_config
        def my_func():
            call_log.append("func")
            return 0

        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("lang: en\n", encoding="utf-8")

        with mock.patch.object(utils_mod, "get_config_path", return_value=cfg_path):
            with mock.patch(
                "multiligua_cli.setup.run_setup"
            ) as setup_mock:
                rc = my_func()

        assert rc == 0
        assert call_log == ["func"]
        setup_mock.assert_not_called()


# ── _save_config ────────────────────────────────────────────────────────────

class TestSaveConfig:
    def test_save_config_writes_valid_yaml(self, tmp_path):
        """_save_config should write a valid YAML file that round-trips."""
        cfg_path = tmp_path / "config.yaml"
        data = {
            "ai": {
                "provider": "openai",
                "model": "gpt-4o",
                "base_url": "https://api.openai.com/v1",
            },
            "lang": "en",
        }
        with mock.patch.object(tui_mod, "get_config_path", return_value=cfg_path):
            tui_mod._save_config(data)

        assert cfg_path.exists()
        loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert loaded["ai"]["provider"] == "openai"
        assert loaded["ai"]["model"] == "gpt-4o"
        assert loaded["lang"] == "en"


# ── get_config_path ─────────────────────────────────────────────────────────

class TestGetConfigPath:
    def test_returns_default_path(self, tmp_path, monkeypatch):
        """get_config_path should return project_root / 'config.yaml'."""
        # We can't easily relocate the project root, but we can verify
        # the function returns a Path with the expected name.
        p = utils_mod.get_config_path()
        assert isinstance(p, Path)
        assert p.name == "config.yaml"

    def test_returns_existing_file_when_config_exists(self, tmp_path, monkeypatch):
        """When config.yaml exists at the returned path, load_config reads it."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("lang: en\n", encoding="utf-8")
        import multiligua_cli.main as main_mod
        with mock.patch.object(utils_mod, "get_config_path", return_value=cfg):
            with mock.patch.object(main_mod, "get_config_path", return_value=cfg):
                data = utils_mod.load_config()
        assert data["lang"] == "en"
