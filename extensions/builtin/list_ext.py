"""

""""
from __future__ import annotations

EXTENSION_NAME = "list-ext"
EXTENSION_PRIORITY = 60


def register_cli(subparsers):
    p = subparsers.add_parser(
        EXTENSION_NAME,
        help=EXTENSION_DESCRIPTION,
    )


def handle_command(args) -> int:
    from extensions import list_extensions
    from multiligua_cli.utils import HAS_RICH, console

    exts = list_extensions()
    if not exts:
        return 0

    if HAS_RICH:
        from rich.table import Table
        from rich import box


        for e in exts:
            desc = e["description"] if getattr(args, "verbose", False) else (e["description"][:60] + "..." if len(e["description"]) > 60 else e["description"])
            table.add_row(
                e["name"],
                e["source"],
                str(e["priority"]),
                desc,
            )

        console.print(table)
    else:
        for e in exts:
            print(f"  ▶ {e['name']}  [{e['source']}]  pri={e['priority']}")
            if getattr(args, "verbose", False) and e["description"]:
                print(f"    {e['description']}")

    return 0
