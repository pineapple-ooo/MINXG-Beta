"""
multiligua_cli/tui_chat.py — MINXG TUI chat (the default `minxg` command).

Minimal, English-only TUI with a recognisable banner up top, a clear
prompt, and a short list of in-loop slash commands. Hot-reload and
search have been removed in this build — install via
`minxg ext add <pkg>` or update via `pip install --upgrade minxg-beta`.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from multiligua_cli.banner import banner_block
from multiligua_cli.utils import (
    Colors,
    colorize,
    console,
    ensure_config,
    load_config,
    print_dim,
    print_error,
    print_info,
    print_success,
)


try:
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False


def _version() -> str:
    try:
        from minxg import VERSION as v
        return v
    except Exception:
        return "0.0.0+unknown"


def print_banner() -> None:
    """Show the MINXG banner — ASCII figure + dim subtitle — at the top of the TUI."""
    fig = banner_block(version=_version(),
                       subtitle_color="\033[38;5;245m")
    sys.stdout.write(fig + "\n")
    sys.stdout.flush()
    print_dim("Type /help for commands, /exit to quit.")


def show_help() -> None:
    body = (
        "In-loop commands:\n"
        "  /help    Show this list\n"
        "  /tools   List available tools\n"
        "  /status  Runtime status\n"
        "  /config  Show config\n"
        "  /log     Recent log entries\n"
        "  /clear   Clear screen and re-print banner\n"
        "  /exit    Quit (Ctrl-D also works)\n"
        "\n"
        "Anything else is sent to the model."
    )
    if HAS_RICH:
        console.print(Panel(body, title="Help", border_style="cyan",
                            box=box.ROUNDED))
    else:
        print_info(body)


def _ensure_orchestrator(config: dict):
    """Build a NexusOrchestrator from the active config; return None on failure."""
    try:
        from multiling.orchestrator import NexusOrchestrator
        ai = config.get("ai", {})
        return NexusOrchestrator(
            ai_base_url=ai.get("base_url"),
            ai_api_key=ai.get("api_key"),
            ai_provider=ai.get("provider", "local"),
            ai_model=ai.get("model"),
        )
    except Exception as e:
        print_error(f"Orchestrator init failed: {e}")
        return None


async def _stream(orch, user_message: str, session_id: Optional[str]):
    """Stream tokens from the orchestrator and render them inline."""
    text_parts = []
    tool_events = []

    if HAS_RICH:
        body = Text()
        with Live(body, console=console, refresh_per_second=12,
                  transient=False) as live:
            async for event in orch.chat_stream(user_message,
                                                session_id=session_id):
                kind = event.get("type")
                if kind == "text":
                    chunk = event.get("content", "")
                    text_parts.append(chunk)
                    body.append(chunk)
                    live.update(body)
                elif kind == "tool_call":
                    tool_events.append({"name": event.get("name")})
                elif kind == "tool_result":
                    tool_events.append({"name": event.get("name"),
                                        "elapsed_ms":
                                            event.get("elapsed_ms", 0)})
                elif kind == "error":
                    body.append(f"\n[red]Error: {event.get('message')}[/red]")
                    live.update(body)
    else:
        sys.stdout.write("\n")
        sys.stdout.flush()
        async for event in orch.chat_stream(user_message,
                                            session_id=session_id):
            kind = event.get("type")
            if kind == "text":
                chunk = event.get("content", "")
                text_parts.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
            elif kind == "tool_call":
                tool_events.append({"name": event.get("name")})
            elif kind == "tool_result":
                tool_events.append({"name": event.get("name"),
                                    "elapsed_ms":
                                        event.get("elapsed_ms", 0)})
            elif kind == "error":
                sys.stdout.write(f"\nError: {event.get('message')}\n")
                sys.stdout.flush()
        sys.stdout.write("\n")

    return "".join(text_parts), tool_events


@ensure_config
def tui_chat(args) -> int:
    """Entry point: print banner, init orchestrator, run chat loop."""
    print_banner()

    config = load_config()
    sys.stdout.write("\n")
    sys.stdout.write(colorize(
        f"  provider: {config.get('ai', {}).get('provider', 'local')}\n"
        f"  model:    {config.get('ai', {}).get('model', '')}\n",
        Colors.DIM,
    ))
    sys.stdout.flush()

    orch = _ensure_orchestrator(config)
    if orch is None:
        return 1

    session_id = None

    while True:
        try:
            sys.stdout.write("\n")
            sys.stdout.write(colorize("you > ", Colors.BOLD, Colors.CYAN))
            sys.stdout.flush()
            user_input = input()
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\n")
            print_success("Bye.")
            return 0

        user_input = user_input.strip()
        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("/exit", "/quit", "exit", "quit"):
            print_success("Bye.")
            return 0
        if cmd == "/help":
            show_help()
            continue
        if cmd == "/clear":
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
            print_banner()
            continue
        if cmd == "/tools":
            from multiligua_cli.main import run_tools
            run_tools(args)
            continue
        if cmd == "/status":
            from multiligua_cli.main import run_status
            run_status(args)
            continue
        if cmd == "/config":
            from multiligua_cli.main import run_config_show
            run_config_show(args)
            continue
        if cmd == "/log":
            print_info("Log file lives at ~/.minxg/logs/ ; use `minxg doctor` to inspect.")
            continue

        try:
            text, tool_events = asyncio.run(
                _stream(orch, user_input, session_id=session_id)
            )
        except Exception as e:
            print_error(f"Chat stream failed: {e}")
            continue

        if tool_events:
            names = ", ".join(sorted({t.get("name", "?") for t in tool_events}))
            sys.stdout.write("\n")
            print_dim(f"  -> tools used: {names}")
            sys.stdout.flush()


if __name__ == "__main__":
    import argparse
    tui_chat(argparse.Namespace())
