"""extensions/builtin/files_ext/__init__.py -- file browser v1.0.0

Cross-platform interactive file browser / selector.

**Enabled by default since v0.19.x** -- the AI needs file-read
capability to be useful out of the box.  ADB and ROOT remain
opt-in because they touch the device privileged surface;
files lives purely in userspace and defaults to ON.

Disable with `minxg ext disable minxg-files` if you really
don't want it.
"""
from __future__ import annotations

import fnmatch
import os

from extensions.loader import set_extension_enabled  # noqa: F401  (re-export)


EXTENSION_NAME = "minxg-files"
EXTENSION_DESCRIPTION = (
    "Cross-platform file browser: list directories, choose files, "
    "multi-select operations"
)
EXTENSION_VERSION = "0.17.1"
EXTENSION_PRIORITY = 50
EXTENSION_SOURCE = "builtin"
EXTENSION_ENABLED = True   # enabled by default since v0.19.x


def handle_command(args) -> int:
    """CLI entry: `minxg ext files <subcommand>`."""
    subcmd = getattr(args, "files_subcommand", None)
    if subcmd == "browse":
        return _browse(args)
    if subcmd == "select":
        return _select(args)
    print("files sub-commands:")
    print("  browse [DIR]    browse a directory (interactive)")
    print("  select PATTERN  glob-style file selector")
    return 0


def _browse(args) -> int:
    directory = getattr(args, "directory", os.getcwd())
    directory = os.path.expanduser(directory)
    if not os.path.isdir(directory):
        print(f"directory does not exist: {directory}")
        return 1
    _display_directory(directory)
    return 0


def _display_directory(directory: str, depth: int = 0,
                       max_items: int = 50,
                       max_depth: int = 2) -> None:
    items = sorted(os.listdir(directory), key=lambda x: (
        not os.path.isdir(os.path.join(directory, x)),
        x.lower(),
    ))
    indent = "  " * depth
    for item in items[:max_items]:
        full = os.path.join(directory, item)
        if os.path.isdir(full):
            count = len(os.listdir(full))
            print(f"{indent}dir  {item}/ ({count} items)")
            if depth < max_depth:
                _display_directory(full, depth + 1, 15,
                                   max_depth=max_depth)
        else:
            size = os.path.getsize(full)
            if size < 1024:
                sz = f"{size}B"
            elif size < 1024 * 1024:
                sz = f"{size/1024:.1f}KB"
            else:
                sz = f"{size/(1024*1024):.1f}MB"
            print(f"{indent}file {item} ({sz})")
    if len(items) > max_items:
        print(f"{indent}... ({len(items) - max_items} more)")


def _select(args) -> int:
    pattern = getattr(args, "pattern", "*")
    directory = getattr(args, "directory", os.getcwd())
    directory = os.path.expanduser(directory)
    found = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                found.append(os.path.join(root, f))
        if len(found) > 200:
            break
    for fp in found[:50]:
        rel = os.path.relpath(fp, directory)
        size = os.path.getsize(fp)
        print(f"  {rel:50s} {size:>8d} bytes")
    print(f"\nfound {len(found)} matching files")
    return 0


def register_cli(subparsers) -> None:
    p = subparsers.add_parser(
        "files", help="file browser (opt-in via `minxg ext add minxg-files`)"
    )
    sp_p = p.add_subparsers(dest="files_subcommand")
    browse = sp_p.add_parser("browse", help="browse a directory")
    browse.add_argument("directory", nargs="?", default=os.getcwd(),
                        help="directory path")
    select = sp_p.add_parser("select", help="glob-style file selector")
    select.add_argument("pattern",
                        help="file pattern (e.g. *.py)")
    select.add_argument("--directory", default=os.getcwd(),
                        help="search directory")


def register_hooks(registry) -> None:
    from extensions import register_hook

    def _inject(tools_list):
        tools_list.append({
            "name": "file_browse",
            "description": "browse a directory structure",
            "category": "file",
        })
        tools_list.append({
            "name": "file_select",
            "description": "select files matching a glob",
            "category": "file",
        })
        return tools_list

    register_hook("tool_interceptor", _inject, priority=40)
