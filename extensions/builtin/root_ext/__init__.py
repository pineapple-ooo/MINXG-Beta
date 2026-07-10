"""
extensions/builtin/root_ext/__init__.py — ROOT tools v1.0.1

Opt-in only: ships with EXTENSION_ENABLED = False; the existence of `su`
on the filesystem by itself is NOT enough to gate this extension. Enable
with `minxg ext add minxg-root`.

ROOT tooling is dangerous (it can mount, set iptables, swap kernels, etc);
shipping it auto-enabled would be irresponsible. Probe-on-call is cheap
and keeps cold-start fast on Termux + Py3.13 where `su` is rarely present.
"""
from __future__ import annotations

import os
import subprocess


EXTENSION_NAME = "minxg-root"
EXTENSION_DESCRIPTION = (
    "ROOT tooling: su execution, mount, iptables, sysctl, SELinux, kernel"
)
EXTENSION_VERSION = "0.17.0"
EXTENSION_PRIORITY = 95
EXTENSION_SOURCE = "builtin"
EXTENSION_ENABLED = False  # opt-in via `minxg ext add minxg-root`


_ROOT_CANDIDATES = (
    "/system/bin/su",
    "/system/xbin/su",
    "/sbin/su",
    "/su/bin/su",
    "/magisk/.core/bin/su",
)


def _root_available() -> bool:
    """Returns True if `su` is reachable and answers a probe command."""
    for path in _ROOT_CANDIDATES:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True
    try:
        r = subprocess.run(["su", "-c", "echo ok"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and "ok" in r.stdout:
            return True
    except Exception:
        pass
    return False


def handle_command(args) -> int:
    if not _root_available():
        print("This device is not rooted; ROOT tooling is not available.")
        print("Install Magisk or SuperSU to enable it.")
        return 1

    subcmd = getattr(args, "root_subcommand", None)
    if subcmd is None:
        print("ROOT sub-commands:")
        print("  check        probe ROOT status")
        print("  shell <CMD>  run as root")
        print("  info         system info (root view)")
        print("  magisk       show Magisk info")
        return 0

    if subcmd == "check":
        try:
            r = subprocess.run(["su", "-c", "id"],
                               capture_output=True, text=True, timeout=5)
            uid = r.stdout.strip() or "unknown"
            print(f"ROOT: unlocked (uid={uid})")
        except Exception as e:
            print(f"ROOT: probe failed: {e}")
        return 0

    if subcmd == "shell":
        cmd = getattr(args, "shell_command", "id")
        r = subprocess.run(["su", "-c", cmd],
                           capture_output=True, text=True, timeout=30)
        print(r.stdout.strip())
        return 0

    if subcmd == "info":
        for title, cmd in [
            ("Kernel",     "uname -a"),
            ("Partitions", "df -h | head -5"),
            ("Mounts",     "mount | head -5"),
            ("Memory",     "free -h"),
        ]:
            r = subprocess.run(["su", "-c", cmd],
                               capture_output=True, text=True, timeout=10)
            print(f"\n=== {title} ===")
            print(r.stdout[:500])
        return 0

    if subcmd == "magisk":
        try:
            r = subprocess.run(["su", "-c", "magisk -c"],
                               capture_output=True, text=True, timeout=5)
            print(r.stdout.strip() or "Magisk not detected")
        except Exception:
            print("Magisk not installed")
        return 0

    print(f"unknown ROOT sub-command: {subcmd}")
    return 1


def register_cli(subparsers):
    """`minxg ext root ...` — opt-in ROOT sub-tree."""
    p = subparsers.add_parser(
        "root", help="ROOT tools (opt-in via `minxg ext add minxg-root`)"
    )
    sp = p.add_subparsers(dest="root_subcommand")
    sp.add_parser("check", help="probe ROOT status")
    sp_shell = sp.add_parser("shell", help="run a command as root")
    sp_shell.add_argument("shell_command", help="shell command")
    sp.add_parser("info", help="system info from a root view")
    sp.add_parser("magisk", help="show Magisk info")


def register_hooks(registry):
    """Each tool only fires when ROOT is reachable AND the extension is enabled."""
    if not _root_available():
        return
    from extensions import register_hook

    def _inject(tools):
        tools.extend([
            {"name": "root_check", "description": "probe device ROOT status", "category": "root"},
            {"name": "root_su", "description": "execute arbitrary command as root", "category": "root"},
            {"name": "root_mount", "description": "mount/unmount a filesystem", "category": "root"},
            {"name": "root_iptables", "description": "manage iptables firewall", "category": "root"},
            {"name": "root_sysctl", "description": "read/write kernel parameters", "category": "root"},
            {"name": "root_lsmod", "description": "list loaded kernel modules", "category": "root"},
            {"name": "root_selinux_status", "description": "check or set SELinux mode", "category": "root"},
            {"name": "root_setprop", "description": "set Android system property", "category": "root"},
            {"name": "root_chroot", "description": "chroot into a directory", "category": "root"},
        ])
        return tools

    register_hook("tool_interceptor", _inject, priority=85)
