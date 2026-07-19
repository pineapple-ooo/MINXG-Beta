"""extensions/builtin/hello.py -- minimal reference extension.

Kept intentionally tiny: this is what `writing-minxg-extensions` (see
`skills/development/writing-minxg-extensions/SKILL.md`) points to as
the smallest complete example of the required contract
(EXTENSION_NAME, EXTENSION_DESCRIPTION, handle_command) plus the two
optional hooks (register_cli, register_hooks).
"""
from __future__ import annotations


EXTENSION_NAME = "hello"
EXTENSION_DESCRIPTION = "Minimal reference extension — prints a greeting."
EXTENSION_PRIORITY = 50
EXTENSION_ENABLED = True
EXTENSION_VERSION = "0.17.2"


def register_cli(subparsers) -> None:
    p = subparsers.add_parser(
        EXTENSION_NAME,
        help=EXTENSION_DESCRIPTION,
    )
    p.add_argument("name", nargs="?", default="World", help="who to greet")
    p.add_argument("--loud", action="store_true", help="shout the greeting")


def handle_command(args) -> int:
    from multiligua_cli.utils import HAS_RICH, Colors, colorize, console

    name = getattr(args, "name", "World")
    loud = getattr(args, "loud", False)
    greeting = f"Hello, {name}!"
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
    # No tool to register — this extension is a CLI-only reference
    # example, deliberately not wired into the chat-agent tool surface.
    pass
