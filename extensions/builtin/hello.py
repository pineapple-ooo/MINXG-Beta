"""


"""
from __future__ import annotations


EXTENSION_NAME = "hello"
EXTENSION_PRIORITY = 50
EXTENSION_ENABLED = True
EXTENSION_VERSION = "0.17.1"



def register_cli(subparsers) -> None:
    p = subparsers.add_parser(
        EXTENSION_NAME,
        help=EXTENSION_DESCRIPTION,
    )




def handle_command(args) -> int:
    from multiligua_cli.utils import HAS_RICH, Colors, colorize, console

    name = getattr(args, "name", "World")
    loud = getattr(args, "loud", False)
    if loud:
        greeting = greeting.upper()

    if HAS_RICH:
        from rich.panel import Panel
        from rich import box

        console.print(
            Panel.fit(
                f"[bold cyan]{greeting}[/bold cyan]",
                box=box.ROUNDED,
            )
        )
    else:
        print(colorize(f"\n  {greeting}", Colors.CYAN, Colors.BOLD))

    return 0




def register_hooks(registry):

    pass
