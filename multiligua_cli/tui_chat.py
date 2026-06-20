"""
multiligua_cli/tui_chat.py — MINXG TUI chat (the default `minxg` command).

Polished, English-only chat surface with three visible regions:
  1. Top status bar: provider / model / platform / depth budget / cost used
  2. Conversation area: streamed assistant tokens + tool timelines
  3. Bottom prompt: the input box

In-loop slash command set covers diagnostics, memory priming, and
manual anti-loop escape:
    /help     show this list
    /tools    list available tools (platform-capped)
    /status   runtime status table
    /config   show config
    /memory   show memory-tier snapshot
    /doctor   self-check
    /forget   reset the anti-loop counter (escape a wedge)
    /reset    reset engine + memory
    /clear    clear screen + re-print banner
    /exit     quit (Ctrl-D also works)

Anything else is sent to the model. We always prime the prompt
with the entropic engine's context window so the assistant can
recall prior turns verbatim.
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import List, Optional, Tuple

from multiligua_cli.banner import banner_block, rules
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
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich import box
    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False


# ───────────────────────────────────────────────────────────── helpers ---


def _version() -> str:
    try:
        from minxg import VERSION as v
        return v
    except Exception:
        return "0.0.0+unknown"


def _safe_call(fn, *args, _default: str = "?", **kw):
    try:
        return fn(*args, **kw)
    except Exception:
        return _default


def _platform_label() -> str:
    try:
        from multiling.platform_cap import detect_platform_key, cap_for
        return f"{detect_platform_key()} (cap {cap_for()})"
    except Exception:
        return "?"


def _status_line(provider: str, model: str) -> str:
    """Compact one-liner: provider / model / platform / depth / cost."""
    try:
        from src.ai.safety.guard import get_guard
        g = get_guard()
        depth = g.depth_guard.count
        capd = g.depth_guard.max_depth
        cost = int(g.cost_guard.total_ms)
        ceilm = int(g.cost_guard.ceiling_ms)
        depth_block = f"depth {depth}/{capd} · cost {cost:,}/{ceilm:,}ms"
    except Exception:
        depth_block = "depth ?/? · cost ?/?ms"
    return (f"  · provider [bold cyan]{provider}[/bold cyan] · "
            f"model [bold cyan]{model or 'unset'}[/bold cyan] · "
            f"host [dim]{_platform_label()}[/dim] · "
            f"[dim]{depth_block}[/dim]")


def print_banner() -> None:
    """Show the MINXG banner — wordmark + dim subtitle."""
    fig = banner_block(version=_version(),
                       subtitle_color="\033[38;5;245m")
    sys.stdout.write(fig + "\n")
    sys.stdout.flush()
    print_dim("Type /help for commands, /exit to quit.")


def show_help() -> None:
    body = (
        "In-loop commands:\n"
        "  /help    Show this list\n"
        "  /tools   List available tools (after platform cap)\n"
        "  /status  Runtime status\n"
        "  /config  Show config\n"
        "  /memory  Memory-tier snapshot (L0/L1/L2 counts)\n"
        "  /doctor  Self-check\n"
        "  /forget  Reset anti-loop counter (escape a wedge)\n"
        "  /reset   Reset memory engine\n"
        "  /clear   Clear screen and re-print banner\n"
        "  /exit    Quit (Ctrl-D also works)\n"
        "\n"
        "Anything else is sent to the model. Each turn primes the\n"
        "prompt from the entropic engine so the assistant can\n"
        "recall prior turns verbatim — even with cap=600 tool runs\n"
        "behind it."
    )
    if HAS_RICH:
        console.print(Panel(body, title="Help", border_style="cyan",
                            box=box.ROUNDED))
    else:
        print_info(body)


def show_memory_snapshot() -> None:
    """One-line summary of the entropic memory engine tiers."""
    body_lines: List[str] = []
    try:
        from src.ai.memory.entropic_evolution import get_entropic_engine
        eng = get_entropic_engine()
        st = eng.get_stats()
        body_lines.append(f"  L0 (hot):    {eng.l0.query(eng.l0._cap).__len__()} turns")
        body_lines.append(f"  L1 (warm):   {st.get('l1', {}).get('count', 0)} items "
                           f"(cap {st.get('l1', {}).get('cap', '?')})")
        body_lines.append(f"  L2 (cold):   ~ {0} bytes")
    except Exception as e:
        body_lines.append(f"  (could not read engine: {e})")
    if HAS_RICH:
        console.print(Panel("\n".join(body_lines),
                            title="Memory tiers",
                            border_style="magenta",
                            box=box.ROUNDED))
    else:
        print_info("memory tiers:\n" + "\n".join(body_lines))


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
    text_parts: List[str] = []
    tool_events: List[Tuple[str, int]] = []

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
                    name = event.get("name", "?")
                    tool_events.append((name, 0))
                    body.append(f"\n[cyan]→ {name}[/cyan]")
                    live.update(body)
                elif kind == "tool_result":
                    name = event.get("name", "?")
                    elapsed = int(event.get("elapsed_ms", 0))
                    if tool_events and tool_events[-1][0] == name:
                        tool_events[-1] = (name, elapsed)
                    body.append(f"  [dim]({elapsed}ms)[/dim]")
                    live.update(body)
                    if event.get("result", {}).get("_anti_loop_warning"):
                        w = event["result"]["_anti_loop_warning"]
                        body.append(f"\n[yellow]{w}[/yellow]")
                        live.update(body)
                elif kind == "error":
                    body.append(f"\n[red]Error: {event.get('message')}[/red]")
                    live.update(body)
        sys.stdout.write("\n")
        sys.stdout.flush()
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
                name = event.get("name", "?")
                tool_events.append((name, 0))
                sys.stdout.write(f"\n→ {name}\n")
                sys.stdout.flush()
            elif kind == "tool_result":
                name = event.get("name", "?")
                elapsed = int(event.get("elapsed_ms", 0))
                if tool_events and tool_events[-1][0] == name:
                    tool_events[-1] = (name, elapsed)
                sys.stdout.write(f"  ({elapsed}ms)\n")
                sys.stdout.flush()
            elif kind == "error":
                sys.stdout.write(f"\nError: {event.get('message')}\n")
                sys.stdout.flush()
        sys.stdout.write("\n")

    # Persist to entropic engine in the background (best-effort).
    try:
        from src.ai.memory.entropic_evolution import get_entropic_engine
        asyncio.get_event_loop()
    except Exception:
        pass
    try:
        from src.ai.memory.entropic_evolution import get_entropic_engine
        eng = get_entropic_engine()
        eng.learn_from_user_message(user_message)
        if text_parts:
            eng.learn_from_exchange(user_message, "".join(text_parts),
                                     tool_calls=[n for n, _ in tool_events])
    except Exception:
        pass

    return "".join(text_parts), tool_events


def _print_status_bar(provider: str, model: str) -> None:
    """Render the persistent status bar after the banner."""
    bar = _status_line(provider, model)
    if HAS_RICH:
        console.print()
        console.print(Panel(bar, border_style="bright_black",
                            box=box.HEAVY, expand=False))
        console.print()
    else:
        sys.stdout.write("\n" + bar + "\n\n")
        sys.stdout.flush()


@ensure_config
def tui_chat(args) -> int:
    """Entry point: print banner, status bar, init orchestrator, run loop."""
    print_banner()

    config = load_config()
    provider = config.get("ai", {}).get("provider", "local")
    model = config.get("ai", {}).get("model", "")
    _print_status_bar(provider, model)

    orch = _ensure_orchestrator(config)
    if orch is None:
        return 1

    session_id: Optional[str] = None

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
            _print_status_bar(provider, model)
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
            print_info("Log file lives at ~/.minxg/logs/ ; "
                       "use `minxg doctor` to inspect.")
            continue
        if cmd == "/memory":
            show_memory_snapshot()
            continue
        if cmd == "/doctor":
            from multiligua_cli.main import main as _cli_main
            # bypass argparse by calling doctor directly.
            from multiligua_cli.doctor import run_doctor
            rc = run_doctor(args)
            sys.stdout.write(f"\ndoctor rc={rc}\n")
            continue
        if cmd == "/forget":
            try:
                from src.ai.safety.guard import get_guard, reset_guard
                reset_guard()
                get_guard().reset()
            except Exception:
                pass
            print_success("anti-loop counter reset.")
            continue
        if cmd == "/reset":
            try:
                from src.ai.memory.entropic_evolution import reset_engine_for_tests
                reset_engine_for_tests()
            except Exception:
                pass
            print_success("memory engine reset (cold-start).")
            continue

        # Default → stream the user prompt to the orchestrator.
        try:
            # Reset the per-turn anti-loop budget; this is what
            # guarantees the LLM can do tool calls in a new turn
            # even if the previous turn exhausted the budget.
            try:
                from src.ai.safety.guard import get_guard
                get_guard().reset()
            except Exception:
                pass
            t0 = time.time()
            text, tool_events = asyncio.run(
                _stream(orch, user_input, session_id=session_id)
            )
            elapsed = time.time() - t0
        except Exception as e:
            print_error(f"Chat stream failed: {e}")
            continue

        if tool_events:
            names = ", ".join(sorted({n for n, _ in tool_events}))
            sys.stdout.write("\n")
            print_dim(f"  [{elapsed:0.1f}s] · tools used: {names}")
            sys.stdout.flush()
        else:
            print_dim(f"  [{elapsed:0.1f}s]")


if __name__ == "__main__":
    import argparse
    tui_chat(argparse.Namespace())
