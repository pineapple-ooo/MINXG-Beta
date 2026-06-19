"""
extensions/builtin/adb_ext/__init__.py — ADB command extension v1.0.1

Opt-in only: ships with EXTENSION_ENABLED = False so it never auto-attaches
when `adb` happens to be on PATH. Enable with `minxg ext add minxg-adb`.

Dependency probing happens inside handle_command (cheap, runs only when
invoked), not at module import — that keeps `minxg tools` cold-start
fast on Termux + Py3.13 where adb may simply not exist.
"""
from __future__ import annotations

import os
import subprocess
import sys


EXTENSION_NAME = "minxg-adb"
EXTENSION_DESCRIPTION = (
    "ADB tooling: manage connected Android devices "
    "(devices/shell/install/logcat/screenshot)"
)
EXTENSION_VERSION = "1.0.1"
EXTENSION_PRIORITY = 90
EXTENSION_SOURCE = "builtin"
EXTENSION_ENABLED = False  # opt-in via `minxg ext add minxg-adb`


def _adb_available() -> bool:
    """Does the `adb` binary respond?"""
    try:
        r = subprocess.run(
            ["adb", "version"], capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def _hint_install() -> None:
    print("Install Android SDK Platform Tools:")
    print("  Linux:   sudo apt install android-tools-adb")
    print("  macOS:   brew install android-platform-tools")
    print("  Termux:  pkg install android-tools")


def handle_command(args) -> int:
    if not _adb_available():
        print("ADB is not active. Install Android SDK Platform Tools.")
        _hint_install()
        return 1

    subcmd = getattr(args, "adb_subcommand", None)
    if subcmd is None:
        print("ADB sub-commands:")
        print("  devices               list connected devices")
        print("  shell <CMD>           run shell command on device")
        print("  install <APK>         install an APK")
        print("  screenshot            save a screenshot")
        print("  logcat                recent log lines")
        return 0

    if subcmd == "devices":
        r = subprocess.run(["adb", "devices", "-l"],
                           capture_output=True, text=True)
        print(r.stdout.strip())
        return 0

    if subcmd == "shell":
        cmd = getattr(args, "shell_command", None)
        if not cmd:
            print("Usage: minxg ext adb shell <CMD>")
            return 1
        r = subprocess.run(["adb", "shell", cmd],
                           capture_output=True, text=True, timeout=30)
        print(r.stdout.strip())
        return 0

    if subcmd == "install":
        apk = getattr(args, "apk_path", "")
        if not apk:
            print("Usage: minxg ext adb install <APK>")
            return 1
        r = subprocess.run(["adb", "install", apk],
                           capture_output=True, text=True, timeout=60)
        print(r.stdout.strip())
        return 0

    if subcmd == "screenshot":
        r = subprocess.run(["adb", "exec-out", "screencap", "-p"],
                           capture_output=True, timeout=10)
        out = os.path.expanduser("~/adb_screenshot.png")
        with open(out, "wb") as f:
            f.write(r.stdout)
        print(f"screenshot saved: {out} ({len(r.stdout)} bytes)")
        return 0

    if subcmd == "logcat":
        r = subprocess.run(["adb", "logcat", "-d", "-t", "50"],
                           capture_output=True, text=True, timeout=10)
        print(r.stdout[-5000:])
        return 0

    print(f"unknown ADB sub-command: {subcmd}")
    return 1


def register_cli(subparsers):
    """`minxg ext adb ...` — opt-in ADB sub-tree."""
    p = subparsers.add_parser(
        "adb", help="ADB tools (opt-in via `minxg ext add minxg-adb`)"
    )
    sp = p.add_subparsers(dest="adb_subcommand")
    sp.add_parser("devices", help="list connected devices")
    sp_shell = sp.add_parser("shell", help="run shell on device")
    sp_shell.add_argument("shell_command", help="shell command")
    sp_install = sp.add_parser("install", help="install an APK")
    sp_install.add_argument("apk_path", help="APK file path")
    sp.add_parser("screenshot", help="save a screenshot")
    sp.add_parser("logcat", help="read recent logcat")


def register_hooks(registry):
    """Each registered AI tool only fires when the extension is enabled."""
    if not _adb_available():
        return
    from extensions import register_hook

    def _inject(tools):
        tools.extend([
            {"name": "adb_devices", "description": "list connected Android devices", "category": "adb"},
            {"name": "adb_shell", "description": "execute a shell command on an Android device", "category": "adb"},
            {"name": "adb_install", "description": "install an APK on a device", "category": "adb"},
            {"name": "adb_uninstall", "description": "uninstall an app from a device", "category": "adb"},
            {"name": "adb_push", "description": "push a file to a device", "category": "adb"},
            {"name": "adb_pull", "description": "pull a file from a device", "category": "adb"},
            {"name": "adb_logcat", "description": "read device logcat", "category": "adb"},
            {"name": "adb_screenshot", "description": "capture a device screenshot", "category": "adb"},
            {"name": "adb_reboot", "description": "reboot an Android device", "category": "adb"},
        ])
        return tools

    register_hook("tool_interceptor", _inject, priority=80)
