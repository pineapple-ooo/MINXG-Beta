"""
multiligua_cli/tui_chat.py - MINXG TUI Chat Mode

Features:
  - Streaming output (token-by-token)
  - Thinking chain display
  - Real-time tool call visualization (name, args, result, elapsed)
  - Session logging (user/model/tool automatically logged)
  - Hot-reload scheduling (auto-update during idle)
  - Global commands: /help /clear /tools /status /log /update /exit /search
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time as time_mod
import urllib.parse
from typing import Optional

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
    print_warning,
)


try:
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.console import Group
    HAS_LIVE = True
except ImportError:
    HAS_LIVE = False




@ensure_config
def tui_chat(args) -> int:
    """Start Rich TUI chat session with logging and hot-reload."""
    if not HAS_LIVE:
        print_error("Requires 'rich' package. Install: pip install rich")
        return 1

    config = load_config()

    
    from multiligua_cli.logger import get_logger
    lg = get_logger()
    lg.session_start()
    print_dim(f"Logging enabled -> {str(lg._today_log_path())}")

    
    try:
        from multiling.orchestrator import NexusOrchestrator
        orch = NexusOrchestrator(
            ai_base_url=config.get("ai", {}).get("base_url"),
            ai_api_key=config.get("ai", {}).get("api_key"),
            ai_provider=config.get("ai", {}).get("provider", "local"),
            ai_model=config.get("ai", {}).get("model"),
        )
    except Exception as e:
        lg.error(f"Orchestrator init failed: {e}")
        print_error(f"Orchestrator init failed: {e}")
        return 1

    
    from multiligua_cli.memory import get_evolution_engine
    memory_engine = get_evolution_engine()
    memory_enabled = config.get("memory", {}).get("enabled", True)

    
    session_id: Optional[str] = None

    
    print_banner()
    print_dim("Type /help for commands, /exit to quit. Logging active.\n")

    
    while True:
        try:
            user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            lg.session_end()
            return 0

        if not user_input:
            continue

        
        cmd = user_input.lower().strip()

        if cmd in ("exit", "quit", "/exit", "/quit"):
            lg.session_end()
            print_info("Goodbye!")
            return 0

        if cmd == "/clear":
            console.clear()
            print_banner()
            continue

        if cmd == "/help":
            show_help()
            continue

        if cmd in ("/tools", "/tool"):
            from multiligua_cli.main import run_tools
            run_tools(args)
            continue

        if cmd == "/status":
            from multiligua_cli.main import run_status
            run_status(args)
            continue

        if cmd == "/log":
            _show_recent_logs(lg)
            continue

        if cmd.startswith("/log "):
            _handle_log_command(lg, user_input[5:].strip())
            continue

        if cmd == "/update":
            _show_update_info()
            continue

        if cmd == "/memory":
            _show_memory_info(memory_engine)
            continue

        if cmd.startswith("/search "):
            query = user_input[8:].strip()
            _handle_search(query, config)
            continue

        
        
        if memory_enabled:
            memory_ctx = memory_engine.get_memory_context()
            if memory_ctx:
                enhanced_input = f"{memory_ctx}\n\n---\nUser input: {user_input}"
            else:
                enhanced_input = user_input
        else:
            enhanced_input = user_input

        lg.user(user_input)

        tool_calls_this_round = []

        result = asyncio.run(_run_streaming_chat(
            orch, enhanced_input, session_id=session_id, logger=lg,
        ))

        for tc in result.get("tool_cards", []):
            if isinstance(tc, dict) and tc.get("tool"):
                tool_calls_this_round.append(tc["tool"])

        lg.model(
            message=result["text"],
            thinking=result["thinking"],
            tool_cards=result["tool_cards"],
        )

        if memory_enabled:
            learned = memory_engine.learn_from_exchange(
                user_msg=user_input,
                assistant_msg=result.get("text", ""),
                tool_calls=tool_calls_this_round,
            )
            if learned:
                print_dim(f"(Learned {learned} preferences)")

    return 0




async def _run_streaming_chat(
    orch,
    user_message: str,
    session_id: Optional[str] = None,
    logger=None,
) -> dict:

    think_parts: list[str] = []
    text_parts: list[str] = []
    tool_events: list[dict] = []

    layout = Layout()
    layout.split_column(
        Layout(name="thinking", size=3, visible=False),
        Layout(name="main", ratio=1),
        Layout(name="tools", size=5, visible=False),
    )

    def _render():
        panels = []

        if think_parts:
            layout["thinking"].visible = True
            panels.append(Panel(
                Text("".join(think_parts), style="dim italic"),
                title="Thinking",
                title_align="left",
                border_style="yellow",
                box=box.ROUNDED,
                padding=(0, 1),
            ))
        else:
            layout["thinking"].visible = False

        content = Text("".join(text_parts)) if text_parts else Text("▊", style="dim blink")
        panels.append(Panel(
            content,
            title="MINXG",
            title_align="left",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        ))

        if tool_events:
            layout["tools"].visible = True
            tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
            tbl.add_column("Tool", style="cyan", no_wrap=True, width=22)
            tbl.add_column("Args / Result", style="white")
            tbl.add_column("Time", style="dim", justify="right", width=8)

            for ev in tool_events[-6:]:
                if ev["type"] == "tool_call":
                    args = json.dumps(ev.get("args", {}), ensure_ascii=False)[:80]
                    tbl.add_row(ev["name"], f"[yellow]->[/yellow] {args}", "")
                elif ev["type"] == "tool_result":
                    res = json.dumps(ev.get("result", {}), ensure_ascii=False)[:120]
                    elapsed = f"{ev.get('elapsed_ms', 0)}ms"
                    tbl.add_row(ev["name"], f"[green]<-[/green] {res}", elapsed)

            panels.append(Panel(tbl, title="Tools", title_align="left",
                                border_style="blue", box=box.ROUNDED, padding=(0, 1)))
        else:
            layout["tools"].visible = False

        return Group(*panels)

    with Live(
        _render(), console=console, refresh_per_second=8,
        transient=False, vertical_overflow="visible",
    ) as live:
        try:
            async for event in orch.chat_stream(user_message, session_id=session_id):
                if event["type"] == "thinking":
                    think_parts.append(event["content"])
                elif event["type"] == "text":
                    text_parts.append(event["content"])
                elif event["type"] == "tool_call":
                    tool_events.append(event)
                    if logger:
                        logger.tool(event["name"], event.get("args", {}),
                                    result=None, elapsed_ms=0)
                elif event["type"] == "tool_result":
                    tool_events.append(event)
                    if logger:
                        logger.tool(event["name"], {},
                                    result=event.get("result"),
                                    elapsed_ms=event.get("elapsed_ms", 0))
                elif event["type"] == "error":
                    text_parts.append(f"\n[red]Error: {event['message']}[/red]")
                    if logger:
                        logger.error(event["message"])
                elif event["type"] == "done":
                    pass

                live.update(_render())

        except Exception as e:
            text_parts.append(f"\n[red]Stream error: {e}[/red]")
            if logger:
                logger.error(str(e), details=str(type(e).__name__))
            live.update(_render())

    card_summary = [
        {"name": tc.get("name", "?"), "elapsed_ms": tc.get("elapsed_ms", 0)}
        for tc in tool_events
        if tc["type"] == "tool_result"
    ]
    return {
        "text": "".join(text_parts),
        "thinking": "".join(think_parts),
        "tool_cards": card_summary,
    }




def show_help():
    """Show help panel with all global commands."""
    console.print(Panel.fit(
        "[bold]MINXG TUI Commands[/bold]\n\n"
        "[cyan]/help[/cyan]    Show this help\n"
        "[cyan]/clear[/cyan]   Clear screen\n"
        "[cyan]/tools[/cyan]   List available tools\n"
        "[cyan]/status[/cyan]  System status\n"
        "[cyan]/search <q>[/cyan]  Web search (AI-powered)\n"
        "[cyan]/log[/cyan]     View recent logs\n"
        "[cyan]/log on[/cyan]  Enable logging\n"
        "[cyan]/log off[/cyan] Disable logging\n"
        "[cyan]/update[/cyan]  Check for updates\n"
        "[cyan]/memory[/cyan]  Memory stats\n"
        "[cyan]/exit[/cyan]    Exit (auto-saves logs)\n\n"
        "[dim]Features:[/dim]\n"
        "  Thinking chain - model reasoning (italic dim)\n"
        "  Tool calls - real-time args + result + elapsed\n"
        "  Session logging - auto-saved per conversation\n"
        "  Hot-reload - auto-update during idle\n"
        "  Memory system - learns your preferences",
        title="Help",
        box=box.ROUNDED,
        border_style="blue",
    ))


def _show_recent_logs(lg):
    """Show recent log entries."""
    logs = lg.recent_logs(20)

    if not logs:
        print_dim("No logs yet. Start a conversation to begin logging.")
        return

    tbl = Table(title="Recent Logs", box=box.SIMPLE, show_header=True)
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("Type", style="bold", width=6)
    tbl.add_column("Content", style="white")

    for i, entry in enumerate(logs[-15:], 1):
        tp = entry.get("type", "?")
        if tp == "user":
            icon = "U"
            content = entry.get("message", "")[:80]
        elif tp == "model":
            icon = "M"
            content = entry.get("message", "")[:80]
        elif tp == "tool":
            icon = "T"
            content = f"{entry.get('name', '?')}() -> {entry.get('elapsed_ms', 0)}ms"
        elif tp == "error":
            icon = "E"
            content = entry.get("message", "")[:80]
        else:
            icon = "I"
            content = entry.get("message", entry.get("action", "?"))[:80]

        style = "green" if tp == "user" else "cyan" if tp == "model" else "yellow" if tp == "tool" else "red" if tp == "error" else "dim"
        tbl.add_row(str(i), f"[{style}]{icon} {tp}[/{style}]", content)

    console.print(tbl)
    print_dim(f"Log file: {lg._today_log_path()}")


def _handle_log_command(lg, subcmd: str):
    """Handle /log <subcommand>."""
    if subcmd in ("on", "enable"):
        lg.enabled = True
        print_success("Logging enabled")
    elif subcmd in ("off", "disable"):
        lg.enabled = False
        print_info("Logging disabled")
    else:
        _show_recent_logs(lg)


def _show_update_info():
    print_dim("Hot-reload from remote has been removed in this build. Use `pip install --upgrade` to update.")


def _show_memory_info(engine):
    """Show memory system stats."""
    stats = engine.get_stats()

    if HAS_LIVE:
        table = Table(title="Memory System", box=box.ROUNDED, border_style="green")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="white")
        table.add_row("Total memories", str(stats["total_memories"]))
        table.add_row("Conversations learned", str(stats["conversations_learned"]))
        for cat, cnt in stats.get("categories", {}).items():
            table.add_row(f"  {cat}", str(cnt))

        tool_stats = engine.get_tool_stats()
        if tool_stats:
            table.add_section()
            table.add_row("[bold]Top tools[/bold]", "")
            for tool, cnt in sorted(tool_stats.items(), key=lambda x: -x[1])[:5]:
                table.add_row(f"  {tool}", str(cnt))

        console.print(table)
    else:
        print(f"\nMemory System")
        print(f"  Total memories: {stats['total_memories']}")
        print(f"  Conversations: {stats['conversations_learned']}")


def _handle_search(query: str, config: dict):
    """Handle /search <query> using configured browser search method."""
    if not query:
        print_info("Usage: /search <query>")
        return

    bs_config = config.get("browser_search", {})
    if not bs_config.get("enabled"):
        print_info("Browser search not configured. Run 'minxg setup' to enable.")
        return

    api_type = bs_config.get("api_type", "user")

    if api_type == "api":
        api_url = bs_config.get("api_url", "")
        api_key = bs_config.get("api_key", "")
        model = bs_config.get("model", "")

        if not api_url:
            print_error("Browser search API URL not set. Run 'minxg setup'.")
            return

        try:
            import urllib.request
            import urllib.parse

            payload = {
                "model": model or "default",
                "query": query,
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if isinstance(result, dict):
                text = result.get("text", result.get("result", result.get("response", str(result))))
            else:
                text = str(result)

            console.print(Panel.fit(
                f"[bold cyan]Search:[/bold cyan] {query}\n\n{text[:2000]}",
                title="AI Search Result",
                box=box.ROUNDED,
                border_style="cyan",
            ))
        except Exception as e:
            print_error(f"Search failed: {e}")

    else:
        
        try:
            import webbrowser
            encoded = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded}"
            webbrowser.open(search_url)
            print_info(f"Opened browser: {query}")
        except Exception as e:
            print_error(f"Could not open browser: {e}")


def print_banner():
    """Show welcome banner."""
    console.print(Panel.fit(
        "[bold cyan]MINXG TUI Chat[/bold cyan]\n\n"
        "Streaming output | Thinking chain | Tool visualization\n"
        "Session logging | Hot-reload | Memory evolution\n\n"
        "[dim]Type /help for commands, /exit to quit.[/dim]",
        title="MINXG v3.5.0",
        box=box.ROUNDED,
        border_style="cyan",
    ))


if __name__ == "__main__":
    tui_chat(argparse.Namespace())
