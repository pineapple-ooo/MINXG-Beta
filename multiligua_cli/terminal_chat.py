"""
multiligua_cli/terminal_chat.py — Terminal chat backed by the OpenHTTP Gateway.

Talks to the Gateway's `/v1/chat/completions` endpoint and renders
tool_cards inline.  Separated from main.py for clarity.
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request

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
def terminal_mode(args) -> int:
    """Run terminal chat mode backed by the OpenHTTP Gateway."""

    config = load_config()
    gw_cfg = config.get("gateway", {})
    base_url = (
        getattr(args, "url", None)
        or f"http://127.0.0.1:{gw_cfg.get('port', 18080)}"
    ).rstrip("/")
    model = getattr(args, "model", None) or config.get("ai", {}).get(
        "model", "MiniMax-M3"
    )
    session_id = getattr(args, "session_id", None) or f"term_{secrets.token_hex(6)}"
    timeout = float(getattr(args, "timeout", 120) or 120)
    messages: list[dict] = []

    

    def post_chat(user_text: str) -> dict:
        messages.append({"role": "user", "content": user_text})
        payload = {
            "model": model,
            "messages": messages,
            "session_id": session_id,
            "stream": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Session-ID": session_id,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    

    def render_tool_cards(cards: list) -> None:
        if not cards:
            return
        if HAS_RICH:
            from rich.table import Table
            from rich import box

            table = Table(title="Tool Cards", box=box.ROUNDED)
            table.add_column("Tool", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Time", justify="right")
            table.add_column("Preview", style="dim")
            for card in cards:
                table.add_row(
                    str(card.get("tool", "")),
                    str(card.get("status", "")),
                    f"{card.get('elapsed_ms', 0)}ms",
                    str(card.get("result_preview", ""))[:90],
                )
            console.print(table)
        else:
            print(colorize("\n╭─── Tool Cards ───", Colors.CYAN))
            for card in cards:
                print(
                    colorize(
                        f"│ {card.get('tool')} [{card.get('status')}] "
                        f"{card.get('elapsed_ms')}ms",
                        Colors.CYAN,
                    )
                )
                preview = str(card.get("result_preview", ""))[:160]
                if preview:
                    print(colorize(f"│   {preview}", Colors.DIM))
            print(colorize("╰" + "─" * 25, Colors.CYAN))

    

    if HAS_RICH:
        from rich.panel import Panel
        from rich import box

        console.print(
            Panel.fit(
                f"[bold cyan]MINXG Terminal Chat[/bold cyan]\n"
                f"Gateway: [yellow]{base_url}[/yellow]\n"
                f"Session: [yellow]{session_id}[/yellow]\n\n"
                "Commands: [yellow]/help[/yellow] [yellow]/clear[/yellow] "
                "[yellow]/exit[/yellow]",
                title="Terminal",
                box=box.ROUNDED,
                style="cyan",
            )
        )
    else:
        print(colorize("\nMINXG Terminal Chat", Colors.CYAN, Colors.BOLD))
        print(colorize(f"Gateway: {base_url}", Colors.DIM))
        print(colorize(f"Session: {session_id}\n", Colors.DIM))

    

    while True:
        try:
            user_input = (
                console.input("\n[bold cyan]You:[/bold cyan] ")
                if HAS_RICH
                else input(colorize("\n👤 You: ", Colors.CYAN, Colors.BOLD))
            ).strip()

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                print_info("Goodbye!")
                return 0
            if user_input.lower() == "/clear":
                if HAS_RICH:
                    console.clear()
                else:
                    os.system("cls" if os.name == "nt" else "clear")
                continue
            if user_input.lower() == "/help":
                print_info(
                    "Commands: /help /clear /exit. "
                    "Tool calls are rendered from Gateway tool_cards."
                )
                continue

            
            try:
                if HAS_RICH:
                    with console.status("[dim]Gateway thinking...[/dim]", spinner="dots"):
                        response = post_chat(user_input)
                else:
                    print(colorize("  🤖 Gateway thinking...", Colors.DIM))
                    response = post_chat(user_input)
            except urllib.error.URLError as e:
                print_error(f"Gateway request failed: {e}")
                print_dim(
                    f"Start it with: python -m gateway.runner "
                    f"--port {gw_cfg.get('port', 18080)}"
                )
                continue

            render_tool_cards(response.get("tool_cards", []))

            choice = (response.get("choices") or [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            if content:
                messages.append({"role": "assistant", "content": content})

            if HAS_RICH:
                from rich.panel import Panel
                from rich import box

                console.print(
                    Panel(
                        content or "[dim](empty)[/dim]",
                        title="[bold green]Assistant[/bold green]",
                        box=box.ROUNDED,
                        style="green",
                        padding=(1, 2),
                    )
                )
            else:
                print(colorize("\n╭─── Assistant ───", Colors.GREEN))
                print(f"  {content}")
                print(colorize("╰" + "─" * 20, Colors.GREEN))

        except KeyboardInterrupt:
            print_info("Goodbye!")
            return 0
