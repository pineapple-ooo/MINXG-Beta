"""
"""
from __future__ import annotations
from typing import List, Optional
import os
from . import ExtensionInfo, ExtensionLoader, get_loader

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None


def browse_extensions(loader: ExtensionLoader = None):
    if loader is None:
        loader = get_loader()

    if not loader.extensions:
        loader.discover()

    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
        HAS_PROMPT_TOOLKIT = True
    except ImportError:
        HAS_PROMPT_TOOLKIT = False

    if HAS_PROMPT_TOOLKIT:
        _browse_tui_ptk(loader)
    else:
        _browse_cli(loader)


def _browse_tui_ptk(loader: ExtensionLoader):
    from prompt_toolkit.shortcuts import radiolist_dialog, yes_no_dialog

    while True:
        extensions = loader.list_all()
        if not extensions:
            action = radiolist_dialog(
                values=[
                ],
            ).run()
            if action == "sample":
                info = loader.install_sample()
                if info:
                    _show_info(info)
            elif action == "scan":
                loader.discover()
            elif action == "back" or action is None:
                break
            continue

        items = []
        for ext in extensions:
            status = "✅" if ext.loaded else ("⏸️" if ext.enabled else "⛔")
            items.append((ext.name, f"{status} {ext.emoji} {ext.name}  [{ext.ext_type}]  {ext.description[:40]}"))


        selected = radiolist_dialog(
            values=items,
        ).run()

        if selected is None or selected == "__back__":
            break
        elif selected == "__sample__":
            info = loader.install_sample()
            if info:
                _show_info(info)
        elif selected == "__discover__":
            discovered = loader.discover()
            if discovered:
                pass
        else:
            ext = loader.get(selected)
            if ext:
                _show_ext_detail(loader, ext)


def _browse_cli(loader: ExtensionLoader):
    extensions = loader.list_all()

    if not extensions:
        return

    for i, ext in enumerate(extensions, 1):
        status = "✅" if ext.loaded else "⏸️"
        print(f"  {i:2d}. {status} {ext.emoji} {ext.name} [{ext.ext_type}]")
        if ext.description:
            print(f"      {ext.description[:80]}")


def _show_ext_detail(loader: ExtensionLoader, ext: ExtensionInfo):
    from prompt_toolkit.shortcuts import radiolist_dialog

    while True:
        text_lines = [
        ]
        if ext.description:
            pass
        if ext.load_error:
            pass
        if ext.loaded:
            pass
        elif ext.enabled:
            pass
        else:
            pass
        action = radiolist_dialog(
            title=f"{ext.emoji} {ext.name}",
            text="\n".join(text_lines),
            values=[
            ],
        ).run()

        if action is None or action == "back":
            break
        elif action == "toggle":
            if ext.enabled:
                loader.disable(ext.name)
            else:
                loader.enable(ext.name)
        elif action == "reload":
            ext.loaded = False
            loader._load_extension(ext)
        elif action == "remove":
            from prompt_toolkit.shortcuts import yes_no_dialog
            loader.remove(ext.name)
            break


def _show_info(info: ExtensionInfo = None, msg: str = None):
    if msg:
        print(f"\n  {msg}")
    if info:
        print(f"  {info.emoji} {info.name} v{info.version}")
        print(f"  {info.description}")


def quick_list(loader: ExtensionLoader = None):
    if loader is None:
        loader = get_loader()
    loader.discover()
    extensions = loader.list_all()

    if HAS_RICH and extensions:

        for ext in extensions:
            status = "✅" if ext.loaded else "⛔"
            table.add_row(status, f"{ext.emoji} {ext.name}", ext.ext_type,
                         ext.version, ext.description[:50] if ext.description else "")

        console.print(table)
    else:
        if not extensions:
            return

        for ext in extensions:
            status = "✅" if ext.loaded else "⛔"
            print(f"  {status} {ext.emoji} {ext.name} v{ext.version} [{ext.ext_type}]")
            if ext.description:
                print(f"      {ext.description[:100]}")


def new_user_wizard():
    loader = get_loader()
    loader.discover()

    print("\n╔══════════════════════════════════════════╗")
    print("╚══════════════════════════════════════════╝")
    print()
    print()

    try:
        inp = None
    except (EOFError, KeyboardInterrupt):
        inp = "y"

    if inp != "n":
        info = loader.install_sample()
        if info:
            print(f"     {info.description}")
    else:
            pass

