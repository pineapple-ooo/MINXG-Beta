"""
"""
from __future__ import annotations
from typing import Dict

from multiligua_cli.extensions import get_loader, ExtensionInfo, ExtensionLoader
from multiligua_cli.extensions.tui import browse_extensions, quick_list, new_user_wizard


def get_extensions():
    loader = get_loader()
    loader.discover()
    return loader.list_all()


def list_extensions():
    loader = get_loader()
    loader.discover()
    return loader.list_all()


def register_cli_extensions(subparsers):
    ext_map = {}

    
    ext_map["ext_list"] = lambda args: cmd_ext_list(args)

    return ext_map


def cmd_ext_list(args):
    quick_list()


def dispatch_extension(ext_map, cmd, args):
    if cmd in ext_map:
        return ext_map[cmd](args)
    return 1
