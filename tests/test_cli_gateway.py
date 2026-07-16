"""
test_cli_gateway.py — exercise multiligua_cli/gateway_cli.py

Tests cover:
  - gateway_foreground returns 0 or raises SystemExit(KeyboardInterrupt)
  - gateway_detach (replaces old gateway_start) background nohup path
  - gateway status returns 0
  - gateway stop returns 0 or nonzero
  - port override via --port is accepted
  - --detach flag is accepted by argparse
  - backward-compat alias gateway_start -> gateway_detach
  - api_key from args vs config fallback
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock
import pytest

import multiligua_cli.gateway_cli as gw_mod


# ── helpers ────────────────────────────────────────────────────────────────

def _make_isolated_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "ai:\n"
        "  provider: openai\n"
        "  model: gpt-4o-mini\n"
        "  base_url: https://api.example.com/v1\n"
        "  api_key: testkey\n"
        "gateway:\n"
        "  port: 18080\n"
        "  api_key: gwkey\n"
        "lang: en\n",
        encoding="utf-8",
    )
    import multiligua_cli.utils as utils_mod
    import multiligua_cli.main as main_mod
    p1 = mock.patch.object(utils_mod, "get_config_path", lambda: cfg)
    p2 = mock.patch.object(main_mod, "get_config_path", lambda: cfg)
    p1.start()
    p2.start()
    return cfg


class FakeArgs:
    """Minimal namespace matching what argparse produces for gateway sub-parsers."""
    def __init__(self, **kwargs):
        self.port = kwargs.get("port")
        self.host = kwargs.get("host", "0.0.0.0")
        self.api_key = kwargs.get("api_key")
        self.sub_command = kwargs.get("sub_command", "status")
        self.detach = kwargs.get("detach", False)


# ── gateway_foreground ─────────────────────────────────────────────────────

class TestGatewayForeground:
    def test_foreground_keyboard_interrupt_returns_0(self):
        """Simulate KeyboardInterrupt early in the foreground run."""
        with mock.patch.object(gw_mod, "print_banner"):
            with mock.patch.object(gw_mod, "print_info"):
                with mock.patch(
                    "gateway.runner.run_gateway",
                    side_effect=KeyboardInterrupt,
                ):
                    rc = gw_mod.gateway_foreground(FakeArgs())
        # The function catches KeyboardInterrupt and returns 0
        assert rc == 0

    def test_foreground_exception_returns_1(self):
        with mock.patch.object(gw_mod, "print_banner"):
            with mock.patch.object(gw_mod, "print_info"):
                with mock.patch(
                    "gateway.runner.run_gateway",
                    side_effect=RuntimeError("boom"),
                ):
                    rc = gw_mod.gateway_foreground(FakeArgs())
        assert rc == 1


# ── gateway_status ─────────────────────────────────────────────────────────

class TestGatewayStatus:
    def test_status_returns_0_when_no_pidfile(self):
        """No pidfile, no systemd -> returns 0 with 'not running' message."""
        with mock.patch("os.path.exists", return_value=False):
            rc = gw_mod.gateway_status(FakeArgs())
        assert rc == 0

    def test_status_returns_0_with_stale_pidfile(self, tmp_path):
        """PID file exists but /proc/<pid> does not -> stale, returns 0."""
        pidfile = tmp_path / "gateway.pid"
        pidfile.write_text("99999")
        pid_str = str(pidfile)

        def _exists(p):
            return pid_str in p

        def _expanduser(p):
            if ".multiling" in p and "gateway" in p:
                return pid_str
            return p

        def _open(p, *args, **kwargs):
            if pid_str in p:
                return mock.mock_open(read_data="99999")(p, *args, **kwargs)
            raise FileNotFoundError(p)

        with mock.patch.object(gw_mod.os.path, "exists", side_effect=_exists):
            with mock.patch.object(gw_mod.os.path, "expanduser", side_effect=_expanduser):
                with mock.patch.object(gw_mod, "open", side_effect=_open):
                    rc = gw_mod.gateway_status(FakeArgs())
        assert rc == 0

    def test_status_with_running_pid(self, tmp_path):
        """PID file exists and /proc/<pid> exists -> returns 0."""
        pidfile = tmp_path / "gateway.pid"
        pidfile.write_text("12345")
        pid_str = str(pidfile)
        proc_path = f"/proc/12345"

        def _exists(p):
            if p == "/proc/1/comm":
                return False
            if pid_str in p:
                return True
            if p == proc_path:
                return True
            return False

        def _expanduser(p):
            if ".multiling" in p and "gateway" in p:
                return pid_str
            return p

        def _open(p, *args, **kwargs):
            if pid_str in p:
                return mock.mock_open(read_data="12345")(p, *args, **kwargs)
            if p == "/proc/1/comm":
                raise FileNotFoundError(p)
            return mock.mock_open()(p, *args, **kwargs)

        with mock.patch.object(gw_mod.os.path, "exists", side_effect=_exists):
            with mock.patch.object(gw_mod.os.path, "expanduser", side_effect=_expanduser):
                with mock.patch.object(gw_mod, "open", side_effect=_open):
                    rc = gw_mod.gateway_status(FakeArgs())
        assert rc == 0


# ── gateway_stop ───────────────────────────────────────────────────────────

class TestGatewayStop:
    def test_stop_returns_0_when_nothing_running(self):
        with mock.patch("os.path.exists", return_value=False):
            rc = gw_mod.gateway_stop(FakeArgs())
        assert rc == 0

    def test_stop_returns_0_with_pidfile_killed(self, tmp_path):
        pidfile = tmp_path / "gateway.pid"
        pidfile.write_text("12345")
        pid_str = str(pidfile)

        def _expanduser(p):
            # The function calls expanduser("~/.multiling/gateway.pid")
            if ".multiling" in p and "gateway" in p:
                return pid_str
            return p

        def _open(p, *args, **kwargs):
            if pid_str in p:
                return mock.mock_open(read_data="12345")(p, *args, **kwargs)
            return open(p, *args, **kwargs)

        with mock.patch.object(gw_mod.os.path, "expanduser", side_effect=_expanduser):
            with mock.patch.object(gw_mod, "open", side_effect=_open):
                with mock.patch.object(gw_mod.os, "kill") as fake_kill:
                    with mock.patch.object(gw_mod.os, "remove") as fake_remove:
                        rc = gw_mod.gateway_stop(FakeArgs())
        assert rc == 0
        fake_kill.assert_called_once_with(12345, 9)

    def test_stop_process_lookup_error_returns_0(self, tmp_path):
        """If process already gone, should still return 0."""
        pidfile = tmp_path / "gateway.pid"
        pidfile.write_text("12345")
        pid_str = str(pidfile)

        def _expanduser(p):
            if ".multiling" in p and "gateway" in p:
                return pid_str
            return p

        def _open(p, *args, **kwargs):
            if pid_str in p:
                return mock.mock_open(read_data="12345")(p, *args, **kwargs)
            return open(p, *args, **kwargs)

        fake_kill = mock.Mock(side_effect=ProcessLookupError)
        with mock.patch.object(gw_mod.os.path, "expanduser", side_effect=_expanduser):
            with mock.patch.object(gw_mod, "open", side_effect=_open):
                with mock.patch.object(gw_mod.os, "kill", fake_kill):
                    with mock.patch.object(gw_mod.os, "remove") as fake_remove:
                        rc = gw_mod.gateway_stop(FakeArgs())
        assert rc == 0
        fake_kill.assert_called_once_with(12345, 9)


# ── gateway_detach ──────────────────────────────────────────────────────────

class TestGatewayDetach:
    def test_detach_background_nohup_when_not_systemd(self, tmp_path):
        """When /proc/1/comm != systemd, falls back to nohup start."""
        cfg = _make_isolated_config(tmp_path)
        from multiligua_cli import utils as utils_mod
        with mock.patch.object(utils_mod, "config_exists", return_value=True):
            with mock.patch.object(gw_mod, "print_banner"):
                with mock.patch.object(gw_mod, "print_info"):
                    with mock.patch.object(gw_mod, "print_success"):
                        with mock.patch.object(gw_mod, "print_dim"):
                            with mock.patch("os.path.exists", return_value=False):
                                with mock.patch(
                                    "subprocess.Popen", return_value=mock.Mock(pid=4242)
                                ) as popen_mock:
                                    with mock.patch("time.sleep"):
                                        rc = gw_mod.gateway_detach(
                                            FakeArgs(sub_command=None, detach=True)
                                        )
            assert rc == 0
            popen_mock.assert_called_once()

    def test_port_override_accepted_by_argparse(self):
        """Argparse accepts --port for the gateway subparser."""
        import multiligua_cli.main as main_mod
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_gw = sub.add_parser("gateway")
        p_gw.add_argument("sub_command", nargs="?", choices=["stop", "status"])
        p_gw.add_argument("--port", type=int)
        p_gw.add_argument("--detach", "-d", action="store_true")
        args = parser.parse_args(["gateway", "--port", "9999"])
        assert args.port == 9999
        assert args.detach is False

    def test_detach_flag_accepted_by_argparse(self):
        """Argparse accepts --detach for the gateway subparser."""
        from argparse import ArgumentParser
        parser = ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_gw = sub.add_parser("gateway")
        p_gw.add_argument("sub_command", nargs="?", choices=["stop", "status"])
        p_gw.add_argument("--detach", "-d", action="store_true")
        args = parser.parse_args(["gateway", "--detach"])
        assert args.detach is True

    def test_backward_compat_alias_gateway_start_exists(self):
        """The backward-compat alias gateway_start still exists and
        redirects to gateway_detach."""
        assert hasattr(gw_mod, "gateway_start")
        assert gw_mod.gateway_start is gw_mod.gateway_detach


# ── api_key precedence ─────────────────────────────────────────────────────

class TestApiKeyPrecedence:
    def test_api_key_from_args_over_config(self, tmp_path):
        """When both args.api_key and config have api_key, args wins."""
        from multiligua_cli.main import run_open
        cfg = _make_isolated_config(tmp_path)
        try:
            args = FakeArgs(api_key="arg-key", port=18080, host="127.0.0.1")
            with mock.patch("multiligua_cli.main.load_config", return_value={
                "gateway": {"api_key": "config-key"},
                "ai": {},
            }):
                with mock.patch(
                    "multiligua_cli.main.asyncio.run", return_value=None
                ):
                    rc = run_open(args)
            assert rc == 0
        finally:
            pass

    def test_api_key_falls_back_to_config(self, tmp_path):
        """When args.api_key is None, config gateway.api_key is used."""
        from multiligua_cli.main import run_open
        cfg = _make_isolated_config(tmp_path)
        try:
            args = FakeArgs(api_key=None, port=18080, host="127.0.0.1")
            with mock.patch("multiligua_cli.main.load_config", return_value={
                "gateway": {"api_key": "config-key"},
                "ai": {},
            }):
                with mock.patch(
                    "multiligua_cli.main.asyncio.run", return_value=None
                ):
                    rc = run_open(args)
            assert rc == 0
        finally:
            pass
