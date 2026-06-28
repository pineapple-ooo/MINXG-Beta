"""
multiligua_cli/interactive.py — Interactive chat via local NexusOrchestrator.

This is the default mode when no subcommand is given.
Talks directly to the AI through the orchestrator (no Gateway needed).
"""
from __future__ import annotations

import os
import sys

from multiligua_cli.utils import (
    HAS_RICH,
    Colors,
    colorize,
    console,
    ensure_config,
    load_config,
    print_dim,
    print_error,
    print_info,
)


@ensure_config
def interactive_mode(args) -> int:
    """Run interactive chat backed by the local NexusOrchestrator."""

    
    if HAS_RICH:
        from rich.panel import Panel
        from rich import box

        console.print(
            Panel.fit(
                "[bold cyan]Welcome to MINXG Chat[/bold cyan]\n\n"
                "Type your messages and press Enter to chat.\n"
                "Use [yellow]↑↓[/yellow] for history, "
                "[yellow]Ctrl+C[/yellow] to exit.\n"
                "Commands: [yellow]/help[/yellow] for help, "
                "[yellow]/clear[/yellow] to clear screen.",
                title="MINXG",
                box=box.ROUNDED,
                style="cyan",
            )
        )
    else:
        print(
            colorize(
                """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║           ███╗   ███╗ █████╗ ███╗   ██╗ ██████╗                  ║
║           ████╗ ████║██╔══██╗████╗  ██║██╔═══██╗                 ║
║           ██╔████╔██║███████║██╔██╗ ██║██║   ██║                 ║
║           ██║╚██╔╝██║██╔══██║██║╚██╗██║██║   ██║                 ║
║           ██║ ╚═╝ ██║██║  ██║██║ ╚████║╚██████╔╝                 ║
║           ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝                  ║
║                                                                  ║
║              Multi-Language AI Orchestration                     ║
╚══════════════════════════════════════════════════════════════════╝
""",
                Colors.CYAN,
                Colors.BOLD,
            )
        )
        print(colorize("  Type your messages and press Enter to chat.\n", Colors.DIM))
        print(
            colorize(
                "  Commands: /help for help, /clear to clear screen.\n",
                Colors.DIM,
            )
        )
        print(colorize("  Press Ctrl+C to exit.\n", Colors.DIM))

    
    try:
        from multiling.orchestrator import NexusOrchestrator

        config = load_config()
        orch = NexusOrchestrator(
            ai_base_url=config.get("ai", {}).get("base_url"),
            ai_api_key=config.get("ai", {}).get("api_key"),
            ai_provider=config.get("ai", {}).get("provider", "local"),
            ai_model=config.get("ai", {}).get("model"),
        )

        chat_history: list[str] = []

        
        while True:
            try:
                user_input = (
                    console.input("\n[bold bright_black]▸[/bold bright_black] ")
                    if HAS_RICH
                    else input(colorize("\n▸ ", Colors.CYAN, Colors.BOLD))
                ).strip()

                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye", "/exit", "/quit"):
                    print_info("Goodbye!")
                    return 0
                if user_input.lower() == "/clear":
                    if HAS_RICH:
                        console.clear()
                    else:
                        os.system("cls" if os.name == "nt" else "clear")
                    continue
                if user_input.lower() == "/help":
                    if HAS_RICH:
                        from rich.panel import Panel
                        from rich import box

                        console.print(
                            Panel.fit(
                                "[bold]Available Commands:[/bold]\n\n"
                                "[yellow]/help[/yellow]   - Show this help\n"
                                "[yellow]/clear[/yellow]  - Clear screen\n"
                                "[yellow]/status[/yellow] - Show system status\n"
                                "[yellow]/tools[/yellow]  - List available tools\n"
                                "[yellow]/exit[/yellow]   - Exit chat",
                                title="Help",
                                box=box.ROUNDED,
                            )
                        )
                    else:
                        print(colorize("\n╭─── Available Commands ───", Colors.CYAN))
                        print(colorize("│ /help   - Show this help", Colors.DIM))
                        print(colorize("│ /clear  - Clear screen", Colors.DIM))
                        print(colorize("│ /status - Show system status", Colors.DIM))
                        print(colorize("│ /tools  - List available tools", Colors.DIM))
                        print(colorize("│ /exit   - Exit chat", Colors.DIM))
                        print(colorize("╰" + "─" * 30, Colors.CYAN))
                    continue
                if user_input.lower() == "/status":
                    from multiligua_cli.main import status
                    status(args)
                    continue
                if user_input.lower() == "/tools":
                    from multiligua_cli.main import list_tools
                    list_tools(args)
                    continue

                chat_history.append(user_input)

                
                if HAS_RICH:
                    with console.status("[dim]Thinking...[/dim]", spinner="dots"):
                        response = orch.chat(user_input)
                else:
                    print(colorize("  🤖 Thinking...", Colors.DIM))
                    response = orch.chat(user_input)

                if HAS_RICH:
                    from rich.panel import Panel
                    from rich import box

                    console.print()
                    console.print(
                        Panel(
                            response,
                            title="[bold green]Assistant[/bold green]",
                            box=box.ROUNDED,
                            style="green",
                            padding=(1, 2),
                        )
                    )
                else:
                    print()
                    print(colorize("╭─── Assistant ───", Colors.GREEN))
                    print(f"  {response}")
                    print(colorize("╰" + "─" * 20, Colors.GREEN))

            except KeyboardInterrupt:
                print_info("Goodbye!")
                return 0

        return 0

    except Exception as e:
        print_error(f"Error in interactive mode: {e}")
        import traceback

        traceback.print_exc()
        return 1
