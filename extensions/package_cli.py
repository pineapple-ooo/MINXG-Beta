"""
extensions/package_cli.py — `minxg ext ...` subcommand dispatch.

Pure-English CLI surface. Subcommands:

    minxg ext list                  show installed extensions
    minxg ext available             show built-in optional extensions
    minxg ext add <slug-or-path>    install a built-in or a user-supplied .py
    minxg ext remove <name>         remove an installed extension
    minxg ext info <name>           show details of one extension
    minxg ext enable <name>         enable without re-installing
    minxg ext disable <name>        disable without removing

Built-in optional extensions (adb / root / files) are NOT enabled at
install time — users opt in explicitly with `minxg ext add minxg-adb`
etc. The `available` subcommand surfaces these so users can see the
menu without reading the docs.
"""

from __future__ import annotations

import sys
import shutil
import argparse
import shutil
from pathlib import Path
from typing import List, Optional

from extensions.loader import (
    ExtensionModule,
    get_extension,
    get_extensions,
    list_extensions,
)
from multiligua_cli.utils import (
    Colors,
    colorize,
    print_dim,
    print_error,
    print_info,
    print_success,
    print_warning,
)


BUILTIN_DIR = Path(__file__).parent / "builtin"
USER_DIR = Path(__file__).parent / "user"

BUILTIN_OPTIONAL = {
    "minxg-adb":  ("adb_ext",  "ADB tools: manage connected Android devices"),
    "minxg-root": ("root_ext", "ROOT tools: su / mount / iptables / sysctl"),
    "minxg-files":("files_ext","Cross-platform interactive file browser"),
}


# ---------------------------------------------------------------------------
# Format helpers — keep English-only output.
# ---------------------------------------------------------------------------

def _row(name: str, src: str, ver: str, state: str, desc: str = "",
         width: int = 78) -> str:
    """Return one formatted row for the `ext list` view."""
    name_col = f"{name:<22}"
    src_col  = f"{src:<10}"
    ver_col  = f"v{ver:<10}" if ver else "           "
    state_col = f"[{state}]"
    line = f"  {name_col} {src_col} {ver_col} {state_col:<10}"
    if desc:
        # Truncate desc to fit.
        budget = width - len(line) - 2
        if budget > 12:
            if len(desc) > budget:
                desc = desc[: budget - 1] + "…"
            line += f"  {desc}"
    return line


def _emit_enabled_state(ext: ExtensionModule) -> str:
    """Map an ext module to a user-facing state string."""
    enabled = getattr(getattr(ext, "module", None), "EXTENSION_ENABLED", True)
    return "enabled" if enabled else "disabled"


def _find_by_name(name: str) -> Optional[ExtensionModule]:
    """Find an installed extension by its EXTENSION_NAME."""
    for ext in get_extensions():
        if ext.name == name or ext.name == f"minxg-{name}":
            return ext
    return None


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_list(args) -> int:
    """`minxg ext list` — show every installed extension and its state."""
    rows = list_extensions()
    if not rows:
        print_info("No extensions installed.")
        print_info("Run `minxg ext available` to see built-in options, "
                   "or `minxg ext add <path>` to install your own.")
        return 0

    header = "  name                  source     version     state      description"
    print_info(header)
    print_dim("  " + "─" * (len(header) - 2))
    for row in rows:
        name = row.get("name", "?")
        src = row.get("source", "?")
        ver = row.get("version", "")
        desc = row.get("description", "")
        # Determine loaded state per loader rules:
        loaded = True  # default: opt-in flag is True unless ext sets it False
        for ext in get_extensions():
            if ext.name == name:
                loaded = getattr(
                    getattr(ext, "module", None),
                    "EXTENSION_ENABLED", True,
                )
                break
        state = "enabled" if loaded else "disabled"
        sys.stdout.write(_row(name, src, ver, state, desc) + "\n")
    sys.stdout.flush()
    return 0


def cmd_available(args) -> int:
    """`minxg ext available` — show built-in optional extensions."""
    print_info("Built-in optional extensions (default OFF, opt-in only):")
    print_dim("  " + "─" * 60)
    for slug, (folder, desc) in BUILTIN_OPTIONAL.items():
        target_dir = BUILTIN_DIR / folder
        marker = "(installed)" if target_dir.exists() else "(available)"
        sys.stdout.write(f"  {slug:<14}  {desc}  {marker}\n")
    sys.stdout.flush()
    print_info("")
    print_info("Install any of them with `minxg ext add <slug>`.")
    return 0


def cmd_add(args) -> int:
    """`minxg ext add <spec>` — install a built-in slug or a local .py path."""
    specs = getattr(args, "spec", None) or []
    rc = 0
    for spec in specs:
        if _install_one(spec) != 0:
            rc = 1
    return rc


def _install_one(spec: str) -> int:
    """Install a single extension spec; return 0 on success."""
    spec_path = Path(spec)

    # 1) Built-in slug
    if spec in BUILTIN_OPTIONAL:
        folder, desc = BUILTIN_OPTIONAL[spec]
        target_dir = USER_DIR / folder
        src_dir = BUILTIN_DIR / folder
        if not src_dir.exists():
            print_error(f"Built-in source missing: {src_dir}")
            return 1
        if target_dir.exists():
            print_warning(f"{spec} is already installed at {target_dir}")
            return 0
        try:
            USER_DIR.mkdir(parents=True, exist_ok=True)
            # Copy every file inside src_dir to target_dir.
            for entry in src_dir.iterdir():
                dest = target_dir / entry.name
                if entry.is_dir():
                    shutil.copytree(entry, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(entry, dest)
            print_success(f"Installed built-in {spec}")
            print_info(f"  Path: {target_dir}")
            print_info("  Run `minxg ext list` to see it.")
            return 0
        except Exception as e:
            print_error(f"Install failed: {e}")
            return 1

    # 2) Local path to a .py file or directory
    if not spec_path.exists():
        print_error(f"Path not found: {spec}")
        return 1

    USER_DIR.mkdir(parents=True, exist_ok=True)

    if spec_path.is_file() and spec_path.suffix == ".py":
        dest = USER_DIR / spec_path.name
        try:
            shutil.copy2(spec_path, dest)
            print_success(f"Installed {spec_path.name} -> {dest}")
            return 0
        except Exception as e:
            print_error(f"Install failed: {e}")
            return 1

    if spec_path.is_dir():
        dest = USER_DIR / spec_path.name
        try:
            shutil.copytree(spec_path, dest, dirs_exist_ok=True)
            print_success(f"Installed package {spec_path.name} -> {dest}")
            return 0
        except Exception as e:
            print_error(f"Install failed: {e}")
            return 1

    print_error(f"Unsupported extension spec: {spec} "
                f"(expected built-in slug, .py file, or directory)")
    return 1


def cmd_remove(args) -> int:
    """`minxg ext remove <name>` — uninstall an extension by name."""
    name = getattr(args, "name", "")
    ext = _find_by_name(name)
    if ext is None:
        print_error(f"Extension not installed: {name}")
        return 1

    # Find its on-disk location via the loader.
    target = Path(ext.path) if getattr(ext, "path", None) else None
    if target is None or not target.exists():
        # Fallback: locate by slug under extensions/user
        if USER_DIR.exists():
            for entry in USER_DIR.iterdir():
                if entry.name.startswith(name.split("minxg-")[-1]):
                    target = entry
                    break

    if target is None or not target.exists():
        print_warning(f"No on-disk record for {name}; skipping filesystem delete.")
    else:
        try:
            if target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)
            print_success(f"Removed {name}")
        except Exception as e:
            print_error(f"Remove failed: {e}")
            return 1
    return 0


def cmd_info(args) -> int:
    """`minxg ext info <name>` — show details of one extension."""
    name = getattr(args, "name", "")
    ext = _find_by_name(name)
    if ext is None:
        print_error(f"Extension not installed: {name}")
        print_info("Run `minxg ext list` to see installed extensions.")
        return 1

    print_info("")
    print_info(f"  Extension:    {ext.name}")
    if hasattr(ext, "module") and hasattr(ext.module, "EXTENSION_VERSION"):
        print_info(f"  Version:      v{ext.module.EXTENSION_VERSION}")
    print_info(f"  Description:  {ext.description}")
    print_info(f"  Source:       {ext.source}")
    print_info(f"  Priority:     {ext.priority}")
    enabled = getattr(getattr(ext, "module", None), "EXTENSION_ENABLED", True)
    print_info(f"  State:        {'enabled' if enabled else 'disabled'}")
    if getattr(ext, "path", None):
        print_info(f"  Path:         {ext.path}")
    print_info("")
    return 0


# ---------------------------------------------------------------------------
# enable / disable — lightweight toggles via a JSON manifest under USER_DIR.
# We don't currently ship a manifest file; the loader uses a per-ext flag.
# This implementation flips a `__enabled__` attribute on the ext module
# at runtime so the user can see immediate effect.
# ---------------------------------------------------------------------------

def cmd_enable(args) -> int:
    name = getattr(args, "name", "")
    ext = _find_by_name(name)
    if ext is None:
        print_error(f"Extension not installed: {name}")
        return 1
    if hasattr(ext, "module") and hasattr(ext.module, "EXTENSION_ENABLED"):
        ext.module.EXTENSION_ENABLED = True
    print_success(f"Enabled {name}")
    return 0


def cmd_disable(args) -> int:
    name = getattr(args, "name", "")
    ext = _find_by_name(name)
    if ext is None:
        print_error(f"Extension not installed: {name}")
        return 1
    if hasattr(ext, "module") and hasattr(ext.module, "EXTENSION_ENABLED"):
        ext.module.EXTENSION_ENABLED = False
    print_success(f"Disabled {name}")
    return 0


# ---------------------------------------------------------------------------
# Dispatch from main.py
# ---------------------------------------------------------------------------

SUB_COMMANDS = {
    "list":      cmd_list,
    "available": cmd_available,
    "add":       cmd_add,
    "remove":    cmd_remove,
    "info":      cmd_info,
    "enable":    cmd_enable,
    "disable":   cmd_disable,
}


def _show_help() -> int:
    """Print ext subcommand help when invoked with no action."""
    print_info("Usage: minxg ext <action> [args]")
    print_info("")
    print_info("Actions:")
    print_info("  list                          List installed extensions")
    print_info("  available                     List built-in optional extensions")
    print_info("  add <slug-or-path>            Install a built-in or local package")
    print_info("  remove <name>                 Remove an installed extension")
    print_info("  info <name>                   Show details of one extension")
    print_info("  enable <name>                 Enable without re-installing")
    print_info("  disable <name>                Disable without removing")
    print_info("")
    print_info("Examples:")
    print_info("  minxg ext available")
    print_info("  minxg ext add minxg-adb")
    print_info("  minxg ext add /path/to/my_ext.py")
    return 0


def dispatch_ext_command(args: argparse.Namespace, action: Optional[str]) -> int:
    """Top-level dispatch used by main.py."""
    if not action:
        return _show_help()
    impl = SUB_COMMANDS.get(action)
    if impl is None:
        print_error(f"Unknown ext action: {action!r}")
        _show_help()
        return 2
    return impl(args)
