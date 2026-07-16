"""
multiligua_cli/tui_chat.py — MINXG TUI chat (the default ``minxg`` command).

A polished **blue-premium** chat surface with:

  1. **Redesigned banner** — authoritative brand panel (no block letters)
  2. **Top status bar** — provider · model (prominent) · host · depth · cost
  3. **AI typing indicator** — animated spinner while waiting for first token
  4. **Thinking indicator** — shows reasoning status (content hidden)
  5. **Slash autocomplete** — command list appears when user types ``/``
  6. **Bottom prompt** — blue prompt prefix with slash-command hints
  7. **Blue premium theme** — deep blues, cyan accents throughout

In-loop slash-command set
-------------------------
  Diagnose / inspect
    /help            Show this list
    /tools           List available tools (platform-capped)
    /status          Runtime status table
    /config          Show the active config
    /memory          Memory-tier snapshot (L0/L1/L2)
    /doctor          Self-check (config + tools + extensions)
  Memory priming
    /forget          Reset the anti-loop counter (escape a wedge)
    /reset           Reset memory engine
  Layout
    /clear           Clear screen and re-paint banner + status bar
    /history         Show last N user/assistant turns in this session
  **In-place reconfig** (no chat restart, saved immediately)
    /setup           Re-run the setup wizard with current config as defaults
    /provider [slug] Pick a provider (interactive if no arg)
    /model [name]    Switch model (interactive picker if no arg)
    /url [URL]       Set or view the API base URL
    /apikey [KEY]    Set or view the API key
    /lang [code]     Switch display language (English-only release)
  Exit
    /exit, /quit     Quit (Ctrl-D also works, empty /quit twice to be safe)

Anything that is **not** a slash command is streamed to the active model.
Each turn primes the prompt from the entropic engine so the assistant can
recall prior turns verbatim — even with cap=600 tool runs behind it.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

from multiligua_cli.utils import (
    console,
    ensure_config,
    get_config_path,
    load_config,
    print_dim,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from multiligua_cli.tui_input import read_line as _read_line
from multiligua_cli.wizard_ui import (
    HAS_READCHAR,
    HAS_RICH as _WIZARD_HAS_RICH,
    MinxgMenu,
    _ansi,
    _wizard_chat_banner,
    prompt,
)

try:
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.console import Group
    from rich import box
    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False

# Single source of "rich available" — prefer the wizard's import (it was
# attempted first), but fall back here if the user has a partial install.
if not _WIZARD_HAS_RICH:
    HAS_RICH = False


# ═══════════════════════════════════════════════════════════════════
#  Constants & blue-premium theme
# ═══════════════════════════════════════════════════════════════════

_BRAND = "MINXG"
_BRAND_FULL = "Multilingual Intelligence eXchange Gateway"

# ── Rich style names + RGB for blue-premium look
_C_BG_DEEP    = "rgb(10,30,80)"       # deepest navy — banner background
_C_BG_PANEL   = "rgb(16,42,105)"      # panel background — notice block
_C_ACCENT     = "bright_cyan"          # bright accent — model name, arrows
_C_BLUE_MID   = "deep_sky_blue3"      # medium blue — borders, secondary
_C_BLUE_DIM   = "rgb(45,85,155)"      # dim blue — labels, descriptions
_C_GOLD       = "gold3"               # brand accent — ◆ symbol only

# ── ANSI fallback palette (256-colour)
_A_BG_DEEP    = "\033[48;5;17m"       # deep navy bg
_A_BG_PANEL   = "\033[48;5;18m"       # panel bg
_A_BLUE       = "\033[38;5;75m"       # medium blue
_A_CYAN       = "\033[38;5;51m"       # bright cyan
_A_DIM_BLUE   = "\033[38;5;60m"       # dim blue
_A_GOLD       = "\033[38;5;220m"     # gold
_A_BOLD       = "\033[1m"
_A_DIM        = "\033[2m"
_A_RESET      = "\033[0m"

# ── Spinner frames for typing / thinking indicators
_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# ── Slash command registry: command → description (used for autocomplete)
_SLASH_COMMANDS: Dict[str, str] = {
    "/help":     "Show this command list",
    "/tools":    "List available tools (platform-capped)",
    "/status":   "Runtime status table",
    "/config":   "Show the active config",
    "/memory":   "Memory-tier snapshot (L0/L1/L2)",
    "/doctor":   "Self-check (config + tools + extensions)",
    "/setup":    "Re-run the setup wizard with current config",
    "/provider": "Switch AI provider — interactive picker",
    "/model":    "Switch model — interactive picker",
    "/url":      "Set or view the API base URL",
    "/apikey":   "Set or view the API key",
    "/lang":     "Switch display language",
    "/history":  "Show last 20 turns in this session",
    "/forget":   "Reset anti-loop counter",
    "/reset":    "Reset memory engine (cold-start)",
    "/clear":    "Clear screen + re-paint banner",
    "/exit":     "Quit (Ctrl-D also works)",
    "/quit":     "Quit (Ctrl-D also works)",
}


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════


def _version() -> str:
    try:
        from minxg import VERSION as v
        return v
    except Exception:
        return "0.0.0+unknown"


def _platform_label() -> str:
    try:
        from multiling.platform_cap import detect_platform_key, cap_for
        return f"{detect_platform_key()} (cap {cap_for()})"
    except Exception:
        return "?"


def _get_model_name(config: dict) -> str:
    """Extract the **actual** configured model name from the live config.

    Falls back to the provider's default model if the field is empty,
    so the UI always shows a real model name, never ``unset`` unless
    truly nothing is configured.
    """
    ai = config.get("ai", {})
    model = ai.get("model", "")
    if not model:
        provider = ai.get("provider", "local")
        try:
            from multiligua_cli.providers import AI_PROVIDERS
            info = AI_PROVIDERS.get(provider, {})
            model = info.get("default_model", "unset")
        except Exception:
            model = "unset"
    return model


def _get_provider_name(config: dict) -> str:
    """Get the human-readable provider name from config."""
    ai = config.get("ai", {})
    provider = ai.get("provider", "local")
    try:
        from multiligua_cli.providers import AI_PROVIDERS
        info = AI_PROVIDERS.get(provider, {})
        return info.get("name", provider)
    except Exception:
        return provider


def _status_line(provider: str, model: str) -> str:
    """Compact one-liner used by both the top status bar and /status.

    The model name is rendered in bright cyan bold so it stands out
    as the most prominent piece of information on the bar.
    """
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

    if HAS_RICH:
        return (
            f"  [bold gold3]provider[/] "
            f"[bold bright_cyan]{provider}[/] "
            f"· [bold bright_cyan]{model or 'unset'}[/] "
            f"· [dim silver]host {_platform_label()}[/] "
            f"· [dim silver]{depth_block}[/]"
        )
    return (
        f"  {Colors.GOLD}{Colors.BOLD}provider{Colors.RESET} "
        f"{Colors.SKY}{Colors.BOLD}{provider}{Colors.RESET} "
        f"· {Colors.SKY}{Colors.BOLD}{model or 'unset'}{Colors.RESET} "
        f"· {Colors.SLATE}host {_platform_label()}{Colors.RESET} "
        f"· {Colors.SLATE}{depth_block}{Colors.RESET}"
    )


def _save_config(config: dict) -> None:
    """Atomically save the config dict back to config.yaml."""
    cfg_path = get_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        print_warning("PyYAML is missing on this Python environment.")
        return
    try:
        tmp_path = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, cfg_path)
        print_success(f"Config saved → {cfg_path}")
    except Exception as e:
        print_error(f"Save failed: {e}")
        print_info("Hint: if config.yaml is locked (Android FUSE, NFS, "
                   "root-only path) run with --write-config-env to "
                   "export the patch into MINXG_CONFIG instead.")


# ═══════════════════════════════════════════════════════════════════
#  Banner — redesigned, authoritative, blue-premium
# ═══════════════════════════════════════════════════════════════════


def print_banner(model_name: str = "", provider_name: str = "") -> None:
    """Render the redesigned blue-premium banner.

    Replaces the previous block-letter wordmark with a clean, authoritative
    brand panel that looks professional in any terminal.

    Layout:
      1. **Brand panel** — deep-navy background, gold ◆, white wordmark
         + full expansion, version, and the active model name in bright
         cyan so the user sees exactly what they're talking to.
      2. **Notice panel** — compact blue-background disclaimer.
    """
    version = _version()

    if HAS_RICH:
        # ── Brand panel — MINXG gold/indigo authoritative banner
        brand = Text()
        brand.append(f"  ◆  MINXG", style=f"bold gold3 on rgb(12,18,40)")
        brand.append(f"\n     {_BRAND_FULL}", style=f"dim white on rgb(12,18,40)")
        brand.append(f"\n     Enterprise AI Orchestration Engine", style=f"dim white on rgb(12,18,40)")
        brand.append(f"\n", style=f"on rgb(12,18,40)")
        if model_name:
            brand.append(f"     ▸ Active model: ", style=f"dim white on rgb(12,18,40)")
            brand.append(model_name, style=f"bold bright_cyan on rgb(12,18,40)")
            brand.append(f"\n", style=f"on rgb(12,18,40)")
        if provider_name:
            brand.append(f"     ▸ Provider: ", style=f"dim white on rgb(12,18,40)")
            brand.append(provider_name, style=f"bright_cyan on rgb(12,18,40)")
            brand.append(f"\n", style=f"on rgb(12,18,40)")
        brand.append(f"     Version {version}", style=f"dim silver on rgb(12,18,40)")

        console.print()
        console.print(Panel(
            brand,
            border_style="bright_blue",
            padding=(1, 2),
            width=72,
            title=f"[bold gold3]◆[/bold gold3]",
            subtitle=f"[dim]v{version}[/dim]",
        ))

        # ── Notice panel — compact blue disclaimer
        notice = Text()
        notice.append(
            "  NO WARRANTY · NO LEGAL ADVICE · ACTOR = USER\n"
            "  MIT-licensed, AS-IS. You are the actor, not MINXG.\n"
            "  Consult a qualified lawyer when the answer matters.\n",
            style="dim white on rgb(16,42,105)",
        )
        console.print(Panel(
            notice,
            border_style="deep_sky_blue3",
            padding=(0, 2),
            width=72,
        ))

        sys.stdout.write("\033[2K\r\n")
        sys.stdout.flush()
        console.print()
    else:
        # ── ANSI fallback — same shape, no rich
        # Brand
        brand_line = f"  {_A_GOLD}{_A_BOLD}◆  MINXG{_A_RESET}  {_A_DIM}{_BRAND_FULL}{_A_RESET}"
        sys.stdout.write(f"{Colors.INDIGO}{Colors.BOLD}╔{bar}╗{Colors.RESET}\n")
        sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{brand_line}{' ' * max(0, 68 - _visual_width(brand_line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        sub_line = f"     Enterprise AI Orchestration Engine"
        sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{_A_DIM}{sub_line}{' ' * max(0, 68 - len(sub_line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        if model_name:
            line = f"     ▸ Active model: {_A_CYAN}{_A_BOLD}{model_name}{_A_RESET}"
            sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{line}{' ' * max(0, 68 - len(line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        if provider_name:
            line = f"     ▸ Provider: {_A_CYAN}{provider_name}{_A_RESET}"
            sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{line}{' ' * max(0, 68 - len(line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        ver_line = f"     Version {version}"
        sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{_A_DIM}{ver_line}{' ' * max(0, 68 - len(ver_line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        sys.stdout.write(f"{Colors.INDIGO}╚{bar}╝{Colors.RESET}\n\n")

        # Notice
        notice_style = Colors.bg("17") + Colors.SLATE
        for ln in [
            "  NO WARRANTY · NO LEGAL ADVICE · ACTOR = USER",
            "  MIT-licensed, AS-IS. You are the actor, not MINXG.",
            "  Consult a qualified lawyer when the answer matters.",
        ]:
            sys.stdout.write(f"{notice_style}{ln}{Colors.RESET}\n")
        sys.stdout.write("\n")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════
#  Help
# ═══════════════════════════════════════════════════════════════════


def show_help(active_provider: str, active_model: str) -> None:
    """In-loop help text — provider/model aware, blue themed."""
    body = (
        f"[{_C_BLUE_DIM}]In-loop commands[/]  ·  "
        f"provider [{_C_ACCENT}]{active_provider}[/]  ·  "
        f"model [bold {_C_ACCENT}]{active_model or 'unset'}[/]\n\n"
        "[bold underline]Diagnostics[/bold underline]\n"
        "  /help            Show this list\n"
        "  /tools           List available tools (platform-capped)\n"
        "  /status          Runtime status table\n"
        "  /config          Show the active config\n"
        "  /memory          Memory-tier snapshot (L0/L1/L2)\n"
        "  /doctor          Self-check (config + tools + extensions)\n\n"
        "[bold underline]In-place reconfig (saved immediately)[/bold underline]\n"
        "  /setup                  Re-run the setup wizard using current config\n"
        "  /provider [slug]        Pick a provider — interactive picker if no arg\n"
        "  /model [name]           Switch model — interactive picker if no arg\n"
        "  /url [URL]              Set or view the API base URL\n"
        "  /apikey [KEY]           Set or view the API key (saved on enter)\n"
        "  /lang [code]            Switch display language\n\n"
        "[bold underline]Memory priming[/bold underline]\n"
        "  /history                Show the last 20 turns in this session\n"
        "  /forget                 Reset the anti-loop counter (escape a wedge)\n"
        "  /reset                  Reset memory engine\n\n"
        "[bold underline]Layout + exit[/bold underline]\n"
        "  /clear                  Clear screen, re-paint banner + status bar\n"
        "  /exit, /quit            Quit (Ctrl-D also works)"
    )
    if HAS_RICH:
        console.print(Panel(
            body,
            title=f"[bold bright_cyan]{_BRAND}[/bold bright_cyan] · help",
            border_style="deep_sky_blue3",
            box=box.HEAVY_HEAD,
            padding=(1, 2),
        ))
    else:
        print_info("Type '/help' anywhere for help.  /exit to quit.")


# ═══════════════════════════════════════════════════════════════════
#  Memory snapshot
# ═══════════════════════════════════════════════════════════════════


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
        body_lines.append(f"  L2 (cold):   ~ 0 bytes")
    except Exception as e:
        body_lines.append(f"  (could not read engine: {e})")
    if HAS_RICH:
        console.print(Panel(
            "\n".join(body_lines),
            title="[bold bright_cyan]Memory tiers[/bold bright_cyan]",
            border_style="deep_sky_blue3",
            box=box.HEAVY_HEAD,
            padding=(1, 2),
        ))
    else:
        print_info("memory tiers:\n" + "\n".join(body_lines))


# ═══════════════════════════════════════════════════════════════════
#  Orchestrator IO
# ═══════════════════════════════════════════════════════════════════


def _ensure_orchestrator(config: dict):
    """Build a NexusOrchestrator from the live config dict."""
    try:
        from multiling.orchestrator import NexusOrchestrator
        ai = config.get("ai", {})
        model = ai.get("model")
        if isinstance(model, str) and model.startswith("/"):
            print_warning(f"Model name '{model}' looks like a language code; resetting to default.")
            model = None
        return NexusOrchestrator(
            ai_base_url=ai.get("base_url"),
            ai_api_key=ai.get("api_key"),
            ai_provider=ai.get("provider", "local"),
            ai_model=model,
        )
    except Exception as e:
        print_error(f"Orchestrator init failed: {e}")
        return None


def _rebuild_orchestrator(config: dict):
    """Hot-reload the orchestrator when in-place commands change state."""
    return _ensure_orchestrator(config)


# ═══════════════════════════════════════════════════════════════════
#  Streaming with animated typing + thinking indicators
# ═══════════════════════════════════════════════════════════════════


async def _stream(orch, user_message: str, session_id: Optional[str],
                  history_list: List[str], model_name: str):
    """Stream tokens with animated typing / thinking indicators.

    Behaviour:
      - Before the first token arrives, show an animated spinner:
        ``⠋ {model} is responding...`` in dim cyan.
      - When the model emits a ``thinking`` event, switch the spinner
        to ``⠋ {model} is thinking...`` in dim magenta.
        **The thinking content is NOT displayed** (no text, no tags).
      - When text tokens arrive, the spinner is replaced by the actual
        streamed text, which builds up in-place.
      - Tool calls and results are rendered inline as before.
    """
    text_parts: List[str] = []
    tool_events: List[Tuple[str, int]] = []
    idx = 0
    state = "idle"  # idle → responding → thinking → text

    # ── Background consumer: pulls events into a queue so the main
    #    loop can update the spinner animation between events.
    queue: asyncio.Queue = asyncio.Queue()

    async def _consume():
        try:
            async for event in orch.chat_stream(user_message,
                                                session_id=session_id):
                await queue.put(event)
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        await queue.put(None)  # sentinel — stream finished

    consumer = asyncio.create_task(_consume())

    sys.stdout.write("\n")
    sys.stdout.flush()

    if HAS_RICH:
        content = Text()  # accumulated visible content

        def _indicator(s: str, i: int) -> Text:
            sp = _SPINNER[i % len(_SPINNER)]
            if s == "thinking":
                return Text(
                    f"  {sp} {model_name} is thinking...",
                    style="dim magenta",
                )
            return Text(
                f"  {sp} {model_name} is responding...",
                style=f"dim {_C_ACCENT}",
            )

        with Live(Text(), console=console, refresh_per_second=24,
                  transient=False) as live:
            while True:
                try:
                    # Poll with a short timeout so we can animate the
                    # spinner while waiting for the next event.
                    event = await asyncio.wait_for(queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    if state in ("idle", "responding", "thinking"):
                        idx += 1
                        ind = _indicator(state, idx)
                        if content:
                            # Show content-so-far + spinner below it
                            live.update(Group(content, Text(""), ind))
                        else:
                            live.update(ind)
                    continue

                if event is None:
                    break

                kind = event.get("type")

                if kind == "text":
                    # Transition out of spinner state
                    if state in ("idle", "responding", "thinking"):
                        state = "text"
                    chunk = event.get("content", "")
                    content.append(chunk)
                    text_parts.append(chunk)
                    live.update(content)

                elif kind == "thinking":
                    # ── Show "thinking" indicator but DO NOT display
                    #    the thinking content or [thinking] tags.
                    state = "thinking"
                    # Still capture for memory engine (no visible tags)
                    text_parts.append(
                        "[thinking]" + event.get("content", "") + "[/thinking]"
                    )
                    # The next timeout tick will render the thinking
                    # spinner; no live.update needed here.

                elif kind == "tool_call":
                    if state in ("idle", "responding", "thinking"):
                        state = "text"
                    name = event.get("name", "?")
                    args = event.get("args") or {}
                    content.append(f"\n[{_C_ACCENT}]→ {name}[/]")
                    if args:
                        try:
                            import json as _json
                            content.append(
                                f"  [dim]{_json.dumps(args, ensure_ascii=False)[:80]}[/dim]"
                            )
                        except Exception:
                            pass
                    tool_events.append((name, 0))
                    live.update(content)

                elif kind == "tool_result":
                    name = event.get("name", "?")
                    elapsed = int(event.get("elapsed_ms", 0))
                    content.append(f"  [dim]({elapsed}ms)[/dim]")
                    if tool_events and tool_events[-1][0] == name:
                        tool_events[-1] = (name, elapsed)
                    res = event.get("result", {})
                    if res.get("_anti_loop_warning"):
                        content.append(
                            f"\n[yellow]{res['_anti_loop_warning']}[/yellow]"
                        )
                    live.update(content)

                elif kind == "error":
                    if state in ("idle", "responding"):
                        state = "text"
                    content.append(
                        f"\n[red]Error: {event.get('message')}[/red]"
                    )
                    live.update(content)

            # ── If no content was produced at all, show a dim note
            if not content:
                live.update(Text("  (no response)", style="dim"))

        await consumer
        sys.stdout.write("\n")
        sys.stdout.flush()

    else:
        # ── ANSI fallback — same logic, plain text
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                if state in ("idle", "responding", "thinking"):
                    idx += 1
                    sp = _SPINNER[idx % len(_SPINNER)]
                    if state == "thinking":
                        sys.stdout.write(
                            f"\r\033[K  {sp} {_A_DIM_BLUE}{model_name}"
                            f" is thinking...{_A_RESET}"
                        )
                    else:
                        sys.stdout.write(
                            f"\r\033[K  {sp} {_A_BLUE}{model_name}"
                            f" is responding...{_A_RESET}"
                        )
                    sys.stdout.flush()
                continue

            if event is None:
                break

            kind = event.get("type")

            if kind == "text":
                if state in ("idle", "responding", "thinking"):
                    sys.stdout.write("\r\033[K")  # clear spinner
                    state = "text"
                chunk = event.get("content", "")
                text_parts.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()

            elif kind == "thinking":
                # Indicator only — no content shown
                state = "thinking"
                text_parts.append(
                    "[thinking]" + event.get("content", "") + "[/thinking]"
                )

            elif kind == "tool_call":
                if state in ("idle", "responding", "thinking"):
                    sys.stdout.write("\r\033[K")
                    state = "text"
                name = event.get("name", "?")
                tool_events.append((name, 0))
                sys.stdout.write(f"\n{_A_CYAN}→ {name}{_A_RESET}\n")
                sys.stdout.flush()

            elif kind == "tool_result":
                name = event.get("name", "?")
                elapsed = int(event.get("elapsed_ms", 0))
                if tool_events and tool_events[-1][0] == name:
                    tool_events[-1] = (name, elapsed)
                sys.stdout.write(f"  {_A_DIM_BLUE}({elapsed}ms){_A_RESET}\n")
                sys.stdout.flush()
                res = event.get("result", {})
                if res.get("_anti_loop_warning"):
                    sys.stdout.write(
                        f"\n\033[33m{res['_anti_loop_warning']}\033[0m\n"
                    )
                    sys.stdout.flush()

            elif kind == "error":
                if state in ("idle", "responding"):
                    sys.stdout.write("\r\033[K")
                sys.stdout.write(
                    f"\n\033[31mError: {event.get('message')}\033[0m\n"
                )
                sys.stdout.flush()

        await consumer

        if not text_parts:
            sys.stdout.write("\r\033[K  (no response)\n")
            sys.stdout.flush()

        sys.stdout.write("\n")
        sys.stdout.flush()

    # ── Persist to entropic engine + session history (best-effort)
    final_text = "".join(text_parts)
    history_list.append(f"> {user_message}")
    history_list.append(
        f"AI > {final_text[:240]}{'…' if len(final_text) > 240 else ''}"
    )

    try:
        from src.ai.memory.entropic_evolution import get_entropic_engine
        eng = get_entropic_engine()
        eng.learn_from_user_message(user_message)
        if final_text:
            eng.learn_from_exchange(
                user_message, final_text,
                tool_calls=[n for n, _ in tool_events],
            )
    except Exception:
        pass

    return final_text, tool_events


# ═══════════════════════════════════════════════════════════════════
#  In-place reconfig command surface
# ═══════════════════════════════════════════════════════════════════


def _cmd_set_provider(chat_state, picker: bool = True) -> Tuple[dict, Optional[object]]:
    """Pick a provider; returns (config, new_orchestrator_or_None)."""
    from multiligua_cli.providers import AI_PROVIDERS
    config = chat_state["config"]
    cur = config.get("ai", {}).get("provider", "")
    keys = list(AI_PROVIDERS.keys())
    if picker or not cur:
        names = [f"{AI_PROVIDERS[k]['emoji']} {AI_PROVIDERS[k]['name']}"
                 for k in keys]
        descs = [AI_PROVIDERS[k]["description"] for k in keys]
        default_idx = keys.index(cur) if cur in keys else 0
        menu = MinxgMenu("Select AI provider", names, descs)
        menu.selected = default_idx
        idx = menu.run()
        if idx is None:
            print_info("Provider unchanged.")
            return config, None
        provider_key = keys[idx]
    else:
        provider_key = cur

    info = AI_PROVIDERS[provider_key]
    config.setdefault("ai", {})
    config["ai"]["provider"] = provider_key
    if not config["ai"].get("base_url"):
        config["ai"]["base_url"] = info["default_url"]
    if not config["ai"].get("model"):
        config["ai"]["model"] = info["default_model"]
    _save_config(config)

    if info["needs_api_key"] and not config["ai"].get("api_key"):
        sys.stdout.write("\n")
        key = prompt("Enter API key (Enter to skip)", password=True)
        if key.strip():
            config["ai"]["api_key"] = key.strip()
            _save_config(config)

    new_orch = _rebuild_orchestrator(config)
    print_success(
        f"Provider switched → {info['name']} "
        f"({provider_key}) · model {config['ai'].get('model')}"
    )
    return config, new_orch


def _cmd_set_model(chat_state, picker: bool = True) -> Tuple[dict, Optional[object]]:
    """Pick / type a model; returns (config, new_orchestrator_or_None)."""
    config = chat_state["config"]
    ai = config.setdefault("ai", {})
    cur = ai.get("model", "")
    provider_key = ai.get("provider", "local")
    provider_info = None
    try:
        from multiligua_cli.providers import AI_PROVIDERS
        provider_info = AI_PROVIDERS.get(provider_key)
    except Exception:
        pass
    base_url = ai.get("base_url", "")
    api_key = ai.get("api_key", "")

    fetched: List[str] = []
    if base_url:
        try:
            import urllib.request, ssl, json as _json
            req = urllib.request.Request(
                base_url.rstrip("/") + "/models",
                headers={"Accept": "application/json",
                         **({"Authorization": f"Bearer {api_key}"} if api_key else {})},
            )
            with urllib.request.urlopen(req, timeout=8,
                                        context=ssl.create_default_context()) as resp:
                data = _json.loads(resp.read().decode())
            if isinstance(data, dict):
                raw = data.get("data") or data.get("models") or []
                for m in raw:
                    n = m.get("id", m.get("name", "")) if isinstance(m, dict) else str(m)
                    if n:
                        fetched.append(n)
                fetched = fetched[:50]
        except Exception:
            pass

    candidates: List[str]
    if fetched:
        candidates = fetched
    elif provider_info:
        candidates = [provider_info["default_model"]]
    else:
        candidates = [cur] if cur else ["gpt-4o-mini"]

    if picker or (len(candidates) == 1 and candidates[0] == cur and cur):
        menu = MinxgMenu(
            "Select model",
            candidates,
            [f"fetched from {provider_key or '?'} " if fetched else "default"] * len(candidates),
        )
        try:
            menu.selected = candidates.index(cur)
        except ValueError:
            menu.selected = 0
        idx = menu.run()
        if idx is None:
            print_info("Model unchanged.")
            return config, None
        chosen = candidates[idx]
    else:
        sys.stdout.write("\n")
        chosen = prompt(f"Enter model name ({cur})", cur or "")
        if not chosen.strip():
            return config, None
        chosen = chosen.strip()

    ai["model"] = chosen
    _save_config(config)
    new_orch = _rebuild_orchestrator(config)
    print_success(f"Model switched → {chosen}")
    return config, new_orch


def _cmd_set_url(chat_state, url: Optional[str] = None) -> Tuple[dict, Optional[object]]:
    config = chat_state["config"]
    ai = config.setdefault("ai", {})
    if url is None:
        sys.stdout.write("\n")
        new = prompt("API base URL", ai.get("base_url", ""))
        if not new.strip():
            return config, None
        url = new.strip()
    ai["base_url"] = url
    _save_config(config)
    new_orch = _rebuild_orchestrator(config)
    print_success(f"API URL set → {url}")
    return config, new_orch


def _cmd_set_apikey(chat_state, key: Optional[str] = None) -> Tuple[dict, Optional[object]]:
    config = chat_state["config"]
    ai = config.setdefault("ai", {})
    if key is None:
        sys.stdout.write("\n")
        new = prompt("API key", ai.get("api_key", ""), password=True)
        if not new.strip():
            return config, None
        key = new.strip()
    ai["api_key"] = key
    _save_config(config)
    new_orch = _rebuild_orchestrator(config)
    display = (key[:4] + "…" + key[-4:]) if len(key) > 8 else "set"
    print_success(f"API key updated ({display})")
    return config, new_orch


def _cmd_set_lang(code_arg: Optional[str]) -> None:
    """Switch display language (English-only release)."""
    try:
        from multiligua_cli.i18n import (
            LANGUAGES, LANG_CODES, set_lang, get_lang,
        )
        if not code_arg:
            keys = list(LANGUAGES.keys())
            names = [f"{LANGUAGES[k]['native']} ({LANGUAGES[k]['name']})"
                     for k in keys]
            descs = [f"  Code: {k}" for k in keys]
            menu = MinxgMenu("Select language", names, descs)
            try:
                menu.selected = keys.index(get_lang())
            except ValueError:
                menu.selected = 0
            idx = menu.run()
            if idx is None:
                print_info("Language unchanged.")
                return
            code_arg = keys[idx]
        if code_arg not in LANGUAGES:
            print_warning(f"Unknown code: {code_arg}. "
                          f"Available: {', '.join(LANG_CODES)}")
            return
        set_lang(code_arg)
        info = LANGUAGES[code_arg]
        config = load_config()
        config["lang"] = code_arg
        _save_config(config)
        print_success(f"Language → {info['native']}")
    except Exception as e:
        print_error(f"/lang failed: {e}")


# ═══════════════════════════════════════════════════════════════════
#  Status bar + prompt
# ═══════════════════════════════════════════════════════════════════


def _print_status_bar(provider: str, model: str) -> None:
    """Render the persistent status bar after the banner."""
    bar = _status_line(provider, model)
    if HAS_RICH:
        console.rule(characters="─", style="bright_blue")
        console.print(bar)
        console.rule(characters="─", style="bright_blue")
    else:
        line = "─" * 60
        sys.stdout.write(f"\033[38;5;33m{line}\033[0m\n")
        sys.stdout.write(bar + "\n")
        sys.stdout.write(f"\033[38;5;33m{line}\033[0m\n\n")
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════
#  Slash-command autocomplete input reader
# ═══════════════════════════════════════════════════════════════════


def _read_input(model_name: str = "") -> Optional[str]:
    """Read one user-input line with slash-command autocomplete.

    When the user types ``/``, a filtered list of matching commands
    appears below the input line in real time.  Tab completes the
    command if there is a single match (or fills the common prefix
    for multiple matches).  On EOF it returns ``None`` (Ctrl-D → exit).
    KeyboardInterrupt surfaces as ``"/exit"``.
    """
    if not HAS_READCHAR:
        # ── Fallback: no autocomplete, simple blue prompt
        sys.stdout.write(f"  {_A_CYAN}❯{_A_RESET} ")
        sys.stdout.flush()
        try:
            return _read_line(prompt_text="")
        except EOFError:
            return None
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            return "/exit"

    try:
        return _read_input_readchar()
    except Exception:
        # If readchar fails for any reason, fall back gracefully
        sys.stdout.write(f"  {_A_CYAN}❯{_A_RESET} ")
        sys.stdout.flush()
        try:
            return _read_line(prompt_text="")
        except EOFError:
            return None
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            return "/exit"


def _read_input_readchar() -> Optional[str]:
    """Character-by-character input with live slash autocomplete.

    Uses ``readchar.readkey()`` which returns full key sequences
    (including escape sequences for arrow keys).  The prompt is a
    blue ``❯`` with no model name inline (the model is already shown
    in the banner and status bar) to keep cursor arithmetic simple.

    Cursor management:
      - The input line is always line N.
      - Hint lines (if any) are lines N+1 .. N+hint_count.
      - After each redraw, the cursor is positioned at the end of
        the buffer on line N.
    """
    import readchar

    buffer = ""
    hint_count = 0  # how many hint lines are currently displayed below

    # Visible cells before the buffer: "  ❯ " = 2 spaces + ❯ + space = 4
    PROMPT_CELLS = 4

    # ── ANSI helpers for hint display
    HIDE = "\033[?25l"
    SHOW = "\033[?25h"

    def _clear_hints():
        """Erase any hint lines currently displayed below the input."""
        nonlocal hint_count
        if hint_count > 0:
            for _ in range(hint_count):
                sys.stdout.write("\033[1B\033[2K")  # down + clear line
            for _ in range(hint_count):
                sys.stdout.write("\033[1A")  # move back up
            hint_count = 0

    def _redraw():
        """Re-render the prompt + buffer + optional hint lines."""
        nonlocal hint_count

        # Clear current line, then clear any old hints below
        sys.stdout.write("\r\033[2K")
        _clear_hints()

        # Render prompt + buffer
        sys.stdout.write(f"  {_A_CYAN}❯{_A_RESET} {buffer}")

        # ── Slash autocomplete: show matching commands below the input
        if (buffer.startswith("/")
                and " " not in buffer
                and len(buffer) >= 1):
            matches = [
                (c, d) for c, d in _SLASH_COMMANDS.items()
                if c.startswith(buffer)
            ]
            if matches:
                hint_lines = []
                for cmd, desc in matches[:8]:
                    # Highlight the already-typed portion in cyan,
                    # the remainder in dim blue
                    typed_part = buffer
                    rest_part = cmd[len(buffer):]
                    desc_short = desc[:35] + "…" if len(desc) > 35 else desc
                    hint_lines.append(
                        f"  {_A_CYAN}{typed_part}{_A_RESET}"
                        f"{_A_DIM_BLUE}{rest_part}{_A_RESET}"
                        f"  {_A_DIM}{desc_short}{_A_RESET}"
                    )
                if len(matches) > 8:
                    hint_lines.append(
                        f"  {_A_DIM}… {len(matches) - 8} more{_A_RESET}"
                    )

                hint_count = len(hint_lines)
                # Write hints on lines below the input.
                # Use \r\n to ensure each hint line starts at column 0.
                sys.stdout.write("\r\n" + "\r\n".join(hint_lines))

                # Move cursor back to the input line, end of buffer
                sys.stdout.write("\r")
                for _ in range(hint_count):
                    sys.stdout.write("\033[1A")
                col = PROMPT_CELLS + len(buffer)
                if col > 0:
                    sys.stdout.write(f"\033[{col}C")

        sys.stdout.flush()

    # ── Initial draw
    sys.stdout.write(HIDE)
    _redraw()
    sys.stdout.write(SHOW)

    while True:
        key = readchar.readkey()

        if not key:
            continue

        # ── Enter → submit
        if key in ("\r", "\n"):
            _clear_hints()
            sys.stdout.write("\n")
            sys.stdout.flush()
            return buffer if buffer else None

        # ── Ctrl-D (EOF) → exit
        if key == "\x04":
            _clear_hints()
            sys.stdout.write("\n")
            return None

        # ── Ctrl-C → exit
        if key == "\x03":
            _clear_hints()
            sys.stdout.write("\n")
            return "/exit"

        # ── Escape → clear buffer
        if key == "\x1b":
            if buffer:
                buffer = ""
                _redraw()
            continue

        # ── Arrow keys → ignore (no history recall yet)
        if key in ("\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D",
                    "\x1bOA", "\x1bOB", "\x1bOC", "\x1bOD"):
            continue

        # ── Backspace / Delete
        if key in ("\x7f", "\x08"):
            if buffer:
                buffer = buffer[:-1]
                _redraw()
            continue

        # ── Tab → autocomplete
        if key == "\t":
            if buffer.startswith("/") and " " not in buffer:
                matches = [c for c in _SLASH_COMMANDS if c.startswith(buffer)]
                if len(matches) == 1:
                    buffer = matches[0] + " "
                    _redraw()
                elif len(matches) > 1:
                    # Complete the common prefix
                    common = os.path.commonprefix(matches)
                    if len(common) > len(buffer):
                        buffer = common
                        _redraw()
            continue

        # ── Regular printable character (including multi-byte UTF-8)
        if len(key) == 1 and ord(key) >= 32:
            buffer += key
            _redraw()
        elif len(key) > 1 and not key.startswith("\x1b"):
            # Multi-byte character (e.g. CJK)
            buffer += key
            _redraw()


# ═══════════════════════════════════════════════════════════════════
#  History view
# ═══════════════════════════════════════════════════════════════════


def _history_view(history: List[str]) -> None:
    """Show the most recent exchanges still in memory."""
    body_lines = history[-20:] if history else ["  (no turns yet)"]
    body = "\n".join(f"  {line}" for line in body_lines)
    if HAS_RICH:
        console.print(Panel(body, title="Session history",
                            border_style="dim blue", box=box.ROUNDED,
                            padding=(0, 2)))
    else:
        sys.stdout.write("\nSession history:\n" + body + "\n")


# ═══════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════


@ensure_config
def tui_chat(args) -> int:
    """Entry point: print banner, status bar, init orchestrator, run loop."""
    config = load_config()
    model_name = _get_model_name(config)
    provider_name = _get_provider_name(config)
    orch = _ensure_orchestrator(config)

    # ── Initial paint: banner + status bar
    print_banner(model_name=model_name, provider_name=provider_name)
    _print_status_bar(provider_name, model_name)

    def _reload(*, provider: Optional[str] = None,
                model: Optional[str] = None) -> None:
        """Re-render status bar and rebind the orchestrator reference."""
        nonlocal config, orch, model_name, provider_name
        config = load_config()
        if provider is not None:
            config.setdefault("ai", {})["provider"] = provider
        if model is not None:
            config.setdefault("ai", {})["model"] = model
        model_name = _get_model_name(config)
        provider_name = _get_provider_name(config)
        _print_status_bar(provider_name, model_name)
        orch = _ensure_orchestrator(config) or orch

    history: List[str] = []
    chat_state = {"config": config}
    session_id: Optional[str] = None

    while True:
        # ── Read input (with slash autocomplete)
        user_input = _read_input(model_name=model_name)

        # Ctrl-D inside _read_input returns None → exit cleanly
        if user_input is None:
            sys.stdout.write("\n")
            print_success("Bye.")
            return 0

        if not user_input:
            continue

        # ── Slash-command dispatch
        cmd, _, arg = user_input.partition(" ")

        if cmd in ("/exit", "/quit", "exit", "quit"):
            print_success("Bye.")
            return 0

        if cmd == "/help":
            show_help(provider_name, model_name)
            continue

        if cmd == "/clear":
            if HAS_RICH:
                console.clear()
            else:
                os.system("cls" if os.name == "nt" else "clear")
            # Reload config to pick up any changes, then re-paint
            config = load_config()
            model_name = _get_model_name(config)
            provider_name = _get_provider_name(config)
            orch = _ensure_orchestrator(config) or orch
            print_banner(model_name=model_name, provider_name=provider_name)
            _print_status_bar(provider_name, model_name)
            continue

        if cmd == "/history":
            _history_view(history)
            continue

        if cmd == "/setup":
            try:
                from multiligua_cli.setup import run_setup
                rc = run_setup()
                if rc == 0:
                    _reload()
                    print_success("Reconfig done. Chat continues with new settings.")
            except Exception as e:
                print_error(f"/setup failed: {e}")
            continue

        if cmd == "/provider":
            arg_key = arg.strip() or None
            non_interactive = bool(arg_key)
            try:
                new_config, new_orch = _cmd_set_provider(
                    chat_state,
                    picker=not non_interactive,
                )
                chat_state["config"] = new_config
                if new_orch is not None:
                    orch = new_orch
                _reload()
            except Exception as e:
                print_error(f"/provider failed: {e}")
            continue

        if cmd == "/model":
            arg_name = arg.strip() or None
            non_interactive = bool(arg_name)
            try:
                new_config, new_orch = _cmd_set_model(
                    chat_state,
                    picker=not non_interactive,
                )
                chat_state["config"] = new_config
                if new_orch is not None:
                    orch = new_orch
                _reload()
            except Exception as e:
                print_error(f"/model failed: {e}")
            continue

        if cmd in ("/url", "/api"):
            arg_url = arg.strip() or None
            try:
                new_config, new_orch = _cmd_set_url(chat_state, arg_url)
                chat_state["config"] = new_config
                if new_orch is not None:
                    orch = new_orch
            except Exception as e:
                print_error(f"/url failed: {e}")
            continue

        if cmd in ("/apikey", "/key"):
            arg_key = arg.strip() or None
            try:
                new_config, new_orch = _cmd_set_apikey(chat_state, arg_key)
                chat_state["config"] = new_config
                if new_orch is not None:
                    orch = new_orch
            except Exception as e:
                print_error(f"/apikey failed: {e}")
            continue

        if cmd == "/lang":
            _cmd_set_lang(arg.strip() or None)
            _reload()
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

        # ── Default → stream the user prompt to the model
        try:
            try:
                from src.ai.safety.guard import get_guard
                get_guard().reset()
            except Exception:
                pass
            t0 = time.time()
            text, tool_events = asyncio.run(
                _stream(orch, user_input, session_id=session_id,
                        history_list=history, model_name=model_name)
            )
            elapsed = time.time() - t0
        except Exception as e:
            print_error(f"Chat stream failed: {e}")
            continue

        if tool_events:
            names = ", ".join(sorted({n for n, _ in tool_events}))
            sys.stdout.write("\n")
            print_dim(f"  [{elapsed:0.1f}s] · tools used: {names}")
        else:
            print_dim(f"  [{elapsed:0.1f}s]")


if __name__ == "__main__":
    import argparse
