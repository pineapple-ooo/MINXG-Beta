"""
test_cli_main.py — focused tests for multiligua_cli/main.py that complement
(not duplicate) the existing test_cli_commands.py surface.

Tests cover:
  - argparse subcommand registration
  - --version output and exit code
  - -v / --verbose flag side-effects
  - --list-extensions behaviour
  - No-arg dispatch to TUI (mock tui_chat)
  - minxg setup dispatches to cmd_setup
  - minxg help prints structured cheatsheet
  - minxg model / api / key / lang write config
  - Unknown command errors nonzero
"""
from __future__ import annotations

import io
import os
import sys
import contextlib
from pathlib import Path
from unittest import mock
import pytest

import multiligua_cli.main as main_mod


# ── helpers ────────────────────────────────────────────────────────────────

def _silent_call(argv, env=None):
    """Invoke main(argv), return (rc, stdout_text)."""
    buf = io.StringIO()
    old_env = os.environ.copy()
    if env is not None:
        os.environ.update(env)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                rc = main_mod.main(argv)
            except SystemExit as e:
                rc = int(getattr(e, "code", 0) or 0)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    return rc, buf.getvalue()


def _make_isolated_config(tmp_path: Path) -> Path:
    """Create a temp config.yaml and patch get_config_path."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "ai:\n"
        "  provider: openai\n"
        "  model: gpt-4o-mini\n"
        "  base_url: https://api.example.com/v1\n"
        "  api_key: testkey\n"
        "lang: en\n",
        encoding="utf-8",
    )
    import multiligua_cli.utils as utils_mod
    p1 = mock.patch.object(utils_mod, "get_config_path", lambda: cfg)
    p2 = mock.patch.object(main_mod, "get_config_path", lambda: cfg)
    p1.start()
    p2.start()
    return cfg


# ── version / flags ─────────────────────────────────────────────────────────

class TestVersionAndFlags:
    def test_version_prints_version_string_and_exits_0(self):
        """--version should print version text and exit 0."""
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            try:
                main_mod.main(["--version"])
            except SystemExit as e:
                assert int(getattr(e, "code", 0) or 0) == 0
        out = buf_out.getvalue()
        # Should contain 'minxg' and a version number
        assert "minxg" in out
        # __version__ is imported in main.py
        assert main_mod.__version__ in out

    def test_verbose_flag_sets_log_level_env(self):
        """-v / --verbose should set MINXG_LOG_LEVEL=INFO."""
        import multiligua_cli.main as cli_main_mod
        buf_out = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_out):
            with mock.patch.object(cli_main_mod, "cmd_setup", return_value=0):
                try:
                    cli_main_mod.main(["--verbose", "setup"])
                except SystemExit:
                    pass
        # The env var should have been set during the call
        assert os.environ.get("MINXG_LOG_LEVEL") == "INFO"
        # Clean up
        os.environ.pop("MINXG_LOG_LEVEL", None)

    def test_short_verbose_flag(self):
        import multiligua_cli.main as cli_main_mod
        buf_out = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_out):
            with mock.patch.object(cli_main_mod, "cmd_setup", return_value=0):
                try:
                    cli_main_mod.main(["-v", "setup"])
                except SystemExit:
                    pass
        assert os.environ.get("MINXG_LOG_LEVEL") == "INFO"
        os.environ.pop("MINXG_LOG_LEVEL", None)

    def test_list_extensions_flag_returns_0(self, tmp_path, capsys):
        """--list-extensions should not crash and return 0."""
        # Ensure config exists so @ensure_config doesn't block
        cfg = _make_isolated_config(tmp_path)
        try:
            rc, out = _silent_call(["--list-extensions"])
        finally:
            # cleanup patches is implicit via tmp_path scope
            pass
        assert rc == 0


# ── CORE_COMMANDS frozenset ────────────────────────────────────────────────

class TestCoreCommands:
    def test_core_commands_contains_all_expected(self):
        expected = {
            "docs", "open", "setup", "model", "api", "key", "lang",
            "config", "status", "tools", "gateway", "update", "ext",
            "skill", "help",
        }
        for cmd in expected:
            assert cmd in main_mod.CORE_COMMANDS, f"missing {cmd} in CORE_COMMANDS"

    def test_core_commands_is_frozenset(self):
        assert isinstance(main_mod.CORE_COMMANDS, frozenset)


# ── subcommand routing ─────────────────────────────────────────────────────

class TestSubcommandRouting:
    def test_setup_dispatches_to_cmd_setup(self, tmp_path):
        cfg = _make_isolated_config(tmp_path)
        try:
            with mock.patch.object(main_mod, "cmd_setup", return_value=0) as m:
                rc, _ = _silent_call(["setup"])
                assert m.called
                assert rc == 0
        finally:
            pass

    def test_help_prints_cheatsheet(self):
        rc, out = _silent_call(["help"])
        assert rc == 0
        assert "MINXG" in out
        assert "minxg setup" in out
        assert "minxg model" in out

    def test_no_args_drops_into_tui(self, tmp_path, monkeypatch):
        """No args should attempt to enter the TUI (we mock it)."""
        cfg = _make_isolated_config(tmp_path)
        try:
            with mock.patch.object(main_mod, "_pick_initial_mode", return_value="chat"):
                with mock.patch(
                    "multiligua_cli.tui_chat.tui_chat", return_value=0
                ) as m:
                    rc = main_mod.main([])
                    assert m.called
                    assert rc == 0
        finally:
            pass

    def test_unknown_command_errors_nonzero(self):
        rc, _ = _silent_call(["this-command-does-not-exist"])
        assert rc != 0


# ── mutating commands ──────────────────────────────────────────────────────

class TestMutatingCommands:
    def test_model_set_writes_config(self, tmp_path):
        cfg = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["model", "gpt-4o"])
        finally:
            pass
        assert rc == 0
        import yaml
        data = yaml.safe_load(cfg.read_text())
        assert data["ai"]["model"] == "gpt-4o"

    def test_api_set_writes_config(self, tmp_path):
        cfg = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["api", "https://example.com/v1"])
        finally:
            pass
        assert rc == 0
        import yaml
        data = yaml.safe_load(cfg.read_text())
        assert data["ai"]["base_url"] == "https://example.com/v1"

    def test_key_set_writes_config(self, tmp_path):
        cfg = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["key", "secret123"])
        finally:
            pass
        assert rc == 0
        import yaml
        data = yaml.safe_load(cfg.read_text())
        assert data["ai"]["api_key"] == "secret123"

    def test_lang_valid_code_writes_config(self, tmp_path):
        cfg = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["lang", "en"])
        finally:
            pass
        assert rc == 0
        import yaml
        data = yaml.safe_load(cfg.read_text())
        assert data["lang"] == "en"

    def test_lang_unknown_code_returns_nonzero(self, tmp_path):
        cfg = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["lang", "klingon"])
        finally:
            pass
        assert rc != 0
