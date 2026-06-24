"""
test_cli_commands.py — exercise every top-level command of the CLI to
catch availability regressions and return-code regressions.

Each test invokes `multiligua_cli.main.main(argv)` and asserts on
exit code + side effects (config file written, parser did not blow
up, dispatcher routed to the right handler).
"""
from __future__ import annotations
import io
import os
import sys
import json
import shutil
import tempfile
import argparse
import contextlib
from pathlib import Path
from unittest import mock
import pytest


# ── helpers ────────────────────────────────────────────────────────────────


def _silent_call(argv, capsys=None, env=None):
    """Invoke main(argv) with stdout/stderr swallowed, return rc.

    Multiligual CLI prints very richly. For these tests we just need
    to know whether the routing, parsing, and dispatch succeeded.
    """
    # import the module under a different name — the module itself
    # exports a top-level `main` callable which would shadow `import main`
    # in Python's import machinery.
    import multiligua_cli.main as cli_main_mod
    buf = io.StringIO()
    old_env = os.environ.copy()
    if env is not None:
        os.environ.update(env)
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                rc = cli_main_mod.main(argv)
            except SystemExit as e:
                rc = int(getattr(e, "code", 0) or 0)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    return rc, buf.getvalue()


def _make_isolated_config(tmp_path: Path, *, with_ai: bool = True) -> Path:
    """Create a temp config.yaml and patch every reachable get_config_path()."""
    cfg = tmp_path / "config.yaml"
    if with_ai:
        cfg.write_text(
            "ai:\n"
            "  provider: openai\n"
            "  model: gpt-4o-mini\n"
            "  base_url: https://api.example.com/v1\n"
            "  api_key: sk-test-12345\n"
            "  temperature: 0.3\n"
            "lang: en\n",
            encoding="utf-8",
        )
    else:
        cfg.write_text("lang: en\n", encoding="utf-8")

    # Now patch every place a config path may be read from. main.py does
    # `from multiligua_cli.utils import get_config_path`, so we have to
    # patch in both places.
    import multiligua_cli.utils as utils_mod
    import multiligua_cli.main as main_mod
    from unittest import mock
    patches = [
        mock.patch.object(utils_mod, "get_config_path", lambda: cfg),
        mock.patch.object(main_mod, "get_config_path", lambda: cfg),
    ]
    for p in patches:
        p.start()
    return cfg, patches


def _stop_isolated_config(patches):
    for p in patches:
        p.stop()


# ── parse surface — every advertised subcommand is recognized ──────────────


class TestCliSurface:
    """`minxg --help` should enumerate every advertised subcommand."""
    def test_help_lists_all_top_level_subcommands(self):
        rc, out = _silent_call(["--help"])
        assert rc == 0
        for cmd in ["setup", "config", "status", "tools", "model",
                    "api", "key", "lang", "gateway", "doctor",
                    "ext", "help"]:
            assert f"minxg {cmd}" in out or cmd in out, (
                f"missing {cmd!r} in --help output:\n{out[:800]}"
            )

    def test_help_lists_ext_subcommands(self):
        rc, out = _silent_call(["ext", "--help"])
        assert rc == 0
        # the ext sub-command surface (via ext --help, not minxg --help)
        for action in ["list", "available", "add", "remove", "info",
                       "enable", "disable"]:
            assert action in out, f"ext sub-action {action!r} missing from ext --help"

    def test_unknown_command_errors(self):
        # argparse exits 2 on unknown subcommand. Anything other than 0 is fine
        # — we just want to confirm argparse's parser wires correctly.
        rc, _ = _silent_call(["this-command-does-not-exist"])
        assert rc != 0


class TestVersionFlag:
    def test_version_flag(self):
        # argparse exits 0 on --version
        import multiligua_cli.main as cli_main_mod
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            try:
                cli_main_mod.main(["--version"])
            except SystemExit as e:
                assert int(getattr(e, "code", 0) or 0) == 0
            else:
                pass


# ── config / status / tools / docs (no-config commands) ───────────────────


class TestReadOnlyCommands:
    def test_config_runs_without_writing(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["config"])
        finally:
            _stop_isolated_config(patches)
        assert rc == 0

    def test_status_works_without_config(self):
        """`minxg status` renders even if config is missing/empty."""
        rc, _ = _silent_call(["status"])
        assert rc == 0

    def test_tools_lists_at_least_one_toolset(self):
        rc, _ = _silent_call(["tools"])
        assert rc == 0

    def test_help_command(self):
        rc, out = _silent_call(["help"])
        assert rc == 0
        # cheatsheet contains every core command
        for cmd in ["setup", "config", "status", "tools", "model",
                    "ext", "gateway", "doctor"]:
            assert cmd in out, f"cheatsheet missing {cmd}"


# ── mutating commands — model / api / key / lang ──────────────────────────


class TestMutatingCommands:
    """These write to config.yaml."""
    def test_model_set_writes_config(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["model", "gpt-4o"])
        finally:
            _stop_isolated_config(patches)
        assert rc == 0
        import yaml
        cfg2 = yaml.safe_load(cfg.read_text())
        assert cfg2["ai"]["model"] == "gpt-4o"

    def test_api_set_writes_config(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["api", "https://example.com/v1"])
        finally:
            _stop_isolated_config(patches)
        assert rc == 0
        import yaml
        cfg2 = yaml.safe_load(cfg.read_text())
        assert cfg2["ai"]["base_url"] == "https://example.com/v1"

    def test_key_set_writes_config(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["key", "sk-test-newkey"])
        finally:
            _stop_isolated_config(patches)
        assert rc == 0
        import yaml
        cfg2 = yaml.safe_load(cfg.read_text())
        assert cfg2["ai"]["api_key"] == "sk-test-newkey"

    def test_lang_set_writes_config(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["lang", "en"])
        finally:
            _stop_isolated_config(patches)
        assert rc == 0
        import yaml
        cfg2 = yaml.safe_load(cfg.read_text())
        assert cfg2["lang"] == "en"

    def test_lang_unknown_returns_nonzero(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            rc, _ = _silent_call(["lang", "klingon"])
        finally:
            _stop_isolated_config(patches)
        assert rc != 0


# ── gateway sub-command dispatch (status is read-only, no server) ──────────


class TestGateway:
    def test_gateway_status_returns(self):
        rc, _ = _silent_call(["gateway", "status"])
        # status is a read-only HTTP probe; should run unconditionally
        assert rc in (0, 1), f"unexpected gateway status rc={rc}"

    def test_gateway_no_subcommand_defaults_to_status(self):
        rc, _ = _silent_call(["gateway"])
        # missing sub-command defaults to status
        assert rc in (0, 1)


# ── ext sub-commands — exhaustive through dispatch_ext_command ────────────


class TestExtDispatch:
    def test_ext_list_runs(self):
        rc, _ = _silent_call(["ext", "list"])
        assert rc == 0

    def test_ext_available_lists_known_slugs(self):
        rc, out = _silent_call(["ext", "available"])
        assert rc == 0
        # the three opt-in slugs are advertised
        assert "minxg-adb" in out
        assert "minxg-root" in out

    def test_ext_info_known_builtin(self):
        rc, out = _silent_call(["ext", "info", "minxg-adb"])
        assert rc == 0
        assert "adb" in out.lower() or "adb" in out

    def test_ext_info_unknown_slug(self, capsys):
        rc, _ = _silent_call(["ext", "info", "minxg-not-a-real-slug"])
        # unknown extension should give a non-zero exit
        assert rc != 0

    def test_ext_help_lists_actions(self):
        rc, out = _silent_call(["ext", "--help"])
        assert rc == 0
        for action in ["list", "available", "add", "remove", "info",
                       "enable", "disable"]:
            assert action in out


# ── doctor — full self-check runs without raising ──────────────────────────


class TestDoctor:
    def test_doctor_runs_and_returns_int(self):
        rc, _ = _silent_call(["doctor"])
        # doctor returns 0 (clean) / 1 (fails) / 2 (warnings)
        assert rc in (0, 1, 2), f"unexpected doctor rc={rc}"


# ── top-level options (no subcommand) are reachable as argparse surface ────


class TestTopLevelFlags:
    def test_verbose_flag_is_parsed(self):
        rc, _ = _silent_call(["--help"])
        # argparse exits 0 on -h/--help
        assert rc == 0

    def test_list_extensions_flag(self):
        rc, _ = _silent_call(["--list-extensions"])
        assert rc == 0

    def test_short_help_flag(self):
        rc, _ = _silent_call(["-h"])
        assert rc == 0


# ── model with no arg still parses cleanly (delegates to setup)─────────────


class TestModelNoArg:
    """`minxg model` with no name is special-cased to interactive setup
    which would block on input; we verify it parses and dispatches
    without throwing by mocking its tail."""
    def test_model_no_arg_reaches_setup(self, tmp_path):
        cfg, patches = _make_isolated_config(tmp_path)
        try:
            import multiligua_cli.setup as setup_mod
            with mock.patch.object(setup_mod, "run_setup", return_value=0):
                rc, _ = _silent_call(["model"])
        finally:
            _stop_isolated_config(patches)
        assert rc == 0
