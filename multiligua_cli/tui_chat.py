"""
multiligua_cli/tui_chat.py — MINXG TUI chat (the default ``minxg`` command).

A polished, English-only chat surface with three visible regions:

  1. **Top status bar**    — provider · model · host platform · depth budget · cost
  2. **Conversation area** — streamed assistant tokens + tool-call timelines + history
  3. **Bottom prompt**     — a multi-line input box with history recall

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
from pathlib import Path
from typing import List, Optional, Tuple

from multiligua_cli.banner import banner_block, rules
from multiligua_cli.utils import (
    Colors,
    colorize,
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
from multiligua_cli.wizard_ui import (
    HAS_READCHAR,
    HAS_RICH as _WIZARD_HAS_RICH,
    MinxgMenu,
    Colors as WColors,
    _ansi,
    print_chat_banner as _wizard_chat_banner,
    prompt,
    print_option_item,
)


try:
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.markdown import Markdown
    from rich import box
    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False


# Single source of "rich available" — prefer the wizard's import (it was
# attempted first), but fall back here if the user has a partial install.
if not _WIZARD_HAS_RICH:
    HAS_RICH = False


# ───────────────────────────────────────────────────────────── helpers ---


# Renamed from "Chat" to "MINXG Chat" in user-facing strings — see CHANGELOG
# 0.12.4.  The CLI command stayed as ``minxg chat`` for backward-compat
# but the in-product banner label and docs now refer to it as
# "MINXG Chat" instead of bare "Chat".
_BRAND = "MINXG Chat"


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


def _status_line(provider: str, model: str) -> str:
    """Compact one-liner used by both the top status bar and /status."""
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
        return (f"  · provider [bold cyan]{provider}[/bold cyan] · "
                f"model [bold cyan]{model or 'unset'}[/bold cyan] · "
                f"host [dim]{_platform_label()}[/dim] · "
                f"[dim]{depth_block}[/dim]")
    return (f"  · provider {provider} · "
            f"model {model or 'unset'} · "
            f"host {_platform_label()} · "
            f"{depth_block}")


def _save_config(config: dict) -> None:
    """Atomically save the config dict back to config.yaml.

    All ``minxg …`` and the new ``/…`` chat commands funnel through here
    so failures print a friendly hint instead of dumping a yaml traceback
    on top of the user the way the previous in-chat configurators did.
    """
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
        print_success(f"Config saved to {cfg_path}")
    except Exception as e:
        print_error(f"Save failed: {e}")
        print_info("Hint: if config.yaml is locked (Android FUSE, NFS, "
                   "root-only path) run with --write-config-env to "
                   "export the patch into MINXG_CONFIG instead.")


# ───────────────────────────────────────────────────────────── banner ---


def print_banner() -> None:
    """Show the MINXG banner — wordmark + dim subtitle.

    Uses the chat-surface variant of the ``wizard_ui`` banner so users
    entering the REPL get a "MINXG Chat" sub-line instead of the
    "setup wizard" one the wizard itself prints.
    """
    _wizard_chat_banner()
    if HAS_RICH:
        console.print(
            f"  [bold gold3]{_BRAND}[/bold gold3]  "
            f"[dim]v{_version()}  ·  type [/dim]"
            f"[bold cyan]/help[/bold cyan][dim] for commands, "
            f"[/dim][bold cyan]/exit[/bold cyan][dim] to quit.[/dim]")
    else:
        sys.stdout.write(
            f"  {_ansi(_BRAND, WColors.GOLD, WColors.BOLD)}  "
            f"v{_version()}  ·  type /help for commands, "
            f"/exit to quit.\n")
    sys.stdout.flush()


# ───────────────────────────────────────────────────────── in-place help


def show_help(active_provider: str, active_model: str) -> None:
    """In-loop help text — provider/model aware so the user sees real values."""
    body = (
        f"In-loop commands  ·  provider [cyan]{active_provider}[/cyan]  ·  "
        f"model [cyan]{active_model or 'unset'}[/cyan]\n\n"
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
        console.print(Panel(body, title=f"[bold cyan]{_BRAND}[/bold cyan] · help",
                            border_style="cyan", box=box.ROUNDED,
                            padding=(1, 2)))
    else:
        print_info("Type '/help' anywhere for help.  /exit to quit.")


# ──────────────────────────────────────────────────────────── snapshots


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


# ─────────────────────────────────────────────────────── orchestrator IO


def _ensure_orchestrator(config: dict):
    """Build a NexusOrchestrator from the live config dict."""
    try:
        from multiling.orchestrator import NexusOrchestrator
        ai = config.get("ai", {})
        model = ai.get("model")
        if isinstance(model, str) and model.startswith("/"):
            # Guard against corrupted config where language code leaked into model field
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
    """Hot-reload the orchestrator when the in-place commands change state.

    Returns the new orchestrator (or ``None`` if the init still fails) so
    the chat loop can swap it in without restarting the session.
    """
    return _ensure_orchestrator(config)


# ────────────────────────────────────────────────── streaming renderers


def _render_event_to_text(event: dict, body: Text) -> None:
    """Append one streamed event to the live ``Text`` widget."""
    kind = event.get("type")
    if kind == "text":
        body.append(event.get("content", ""))
    elif kind == "thinking":
        # 0.16.0 — wrap the model's CoT in ``[thinking]...[/thinking]`` so the
        # user can distinguish reasoning from the final answer at a glance
        # even when the output is exported to markdown or replayed through
        # the experimental ``minxg replay`` verb later.
        body.append("\n[dim italic][[thinking]]" +
                    event.get("content", "") + "[[/thinking]][/dim italic]\n")
    elif kind == "tool_call":
        name = event.get("name", "?")
        args = event.get("args") or {}
        body.append(f"\n[cyan]→ {name}[/cyan]")
        if args:
            try:
                import json as _json
                body.append(f"  [dim]{_json.dumps(args, ensure_ascii=False)[:80]}[/dim]")
            except Exception:
                pass
    elif kind == "tool_result":
        name = event.get("name", "?")
        elapsed = int(event.get("elapsed_ms", 0))
        body.append(f"  [dim]({elapsed}ms)[/dim]")
        if event.get("result", {}).get("_anti_loop_warning"):
            w = event["result"]["_anti_loop_warning"]
            body.append(f"\n[yellow]{w}[/yellow]")
    elif kind == "error":
        body.append(f"\n[red]Error: {event.get('message')}[/red]")


async def _stream(orch, user_message: str, session_id: Optional[str],
                  history_list: List[str]):
    """Stream tokens from the orchestrator and render them inline."""
    text_parts: List[str] = []
    tool_events: List[Tuple[str, int]] = []

    sys.stdout.write("\n")
    sys.stdout.flush()

    if HAS_RICH:
        body = Text()
        with Live(body, console=console, refresh_per_second=24,
                  transient=False) as live:
            async for event in orch.chat_stream(user_message,
                                                session_id=session_id):
                _render_event_to_text(event, body)
                live.update(body)
                if event.get("type") == "text":
                    text_parts.append(event.get("content", ""))
                elif event.get("type") == "thinking":
                    # Capture thinking for the final text too — that way
                    # markdown / log replays still contain the
                    # ``[thinking]...[/thinking]`` block, not just the dim rich
                    # formatted in-line view.
                    text_parts.append("[thinking]" +
                                      event.get("content", "") + "[/thinking]")
                elif event.get("type") == "tool_call":
                    tool_events.append((event.get("name", "?"), 0))
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        async for event in orch.chat_stream(user_message,
                                            session_id=session_id):
            kind = event.get("type")
            if kind == "text":
                chunk = event.get("content", "")
                text_parts.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
            elif kind == "thinking":
                # Mirror the rich life-renderer's behaviour but as plain
                # text wrapped in ``[thinking]...[/thinking]`` so downstream
                # markdown replays / non-rich output still knows which
                # slice is reasoning vs the answer.
                think_chunk = "[thinking]" + event.get("content", "") + "[/thinking]"
                text_parts.append(think_chunk)
                sys.stdout.write(think_chunk)
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
                res = event.get("result", {})
                if res.get("_anti_loop_warning"):
                    sys.stdout.write(f"\n{res['_anti_loop_warning']}\n")
                    sys.stdout.flush()
            elif kind == "error":
                sys.stdout.write(f"\nError: {event.get('message')}\n")
                sys.stdout.flush()
        sys.stdout.write("\n")

    # Persist to entropic engine + session history (best-effort).
    final_text = "".join(text_parts)
    history_list.append(f"> {user_message}")
    history_list.append(f"AI > {final_text[:240]}{'…' if len(final_text) > 240 else ''}")

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


# ────────────────────────────────── in-place reconfig command surface


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

    # Pull a fresh API-key prompt if needed and the user hasn't set one yet.
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


# ───────────────────────────────────────────────── status bar + prompt


def _print_status_bar(provider: str, model: str) -> None:
    """Render the persistent status bar after the banner."""
    bar = _status_line(provider, model)
    if HAS_RICH:
        console.rule(characters="─", style="bright_black")
        console.print(bar)
        console.rule(characters="─", style="bright_black")
    else:
        sys.stdout.write(_ansi(rules(60), "\033[38;5;245m") + "\n")
        sys.stdout.write(bar + "\n")
        sys.stdout.write(_ansi(rules(60), "\033[38;5;245m") + "\n\n")
        sys.stdout.flush()


def _print_prompt() -> None:
    """Draw the bottom prompt prefix only (input itself is up to the host).

    Note: the leading user identity ("you") was removed in v0.13.2 —
    a single-arrow prefix is enough; the chat turn buffer already
    distinguishes who's speaking without needing a redundant label here.
    """
    if HAS_RICH:
        sys.stdout.write("\n")
        console.print("  [bold bright_black]▸[/bold bright_black] ",
                      end="")
    else:
        sys.stdout.write("\n  " + _ansi("▸", "") + " ")
    sys.stdout.flush()


def _read_input() -> Optional[str]:
    """Read one user-input line (multi-line via trailing backslash)."""
    buf: List[str] = []
    sys.stdout.flush()
    try:
        while True:
            chunk = input()
            if chunk.endswith("\\"):
                buf.append(chunk[:-1])
                sys.stdout.write("       " + _ansi("…", "\033[38;5;245m") + " ")
            else:
                buf.append(chunk)
                break
        return "\n".join(buf).strip()
    except EOFError:
        return None  # sentinel for Ctrl-D → /exit
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return "/exit"


def _history_view(history: List[str]) -> None:
    """Show the most recent exchanges still in memory."""
    body_lines = history[-20:] if history else ["  (no turns yet)"]
    body = "\n".join(f"  {line}" for line in body_lines)
    if HAS_RICH:
        console.print(Panel(body, title="Session history",
                            border_style="dim", box=box.ROUNDED,
                            padding=(0, 2)))
    else:
        sys.stdout.write("\nSession history:\n" + body + "\n")


# ──────────────────────────────────────────────────────── main entry ---


@ensure_config
def tui_chat(args) -> int:
    """Entry point: print banner, status bar, init orchestrator, run loop."""
    print_banner()
    config = load_config()

    def _reload(*, provider: Optional[str] = None,
                model: Optional[str] = None) -> None:
        """Re-render status bar and rebind the orchestrator reference."""
        nonlocal config, orch
        config = load_config()
        if provider is not None:
            config.setdefault("ai", {})["provider"] = provider
        if model is not None:
            config.setdefault("ai", {})["model"] = model
        provider_now = config.get("ai", {}).get("provider", "local")
        model_now = config.get("ai", {}).get("model", "")
        _print_status_bar(provider_now, model_now)
        orch = _ensure_orchestrator(config) or orch

    _reload()

    history: List[str] = []
    chat_state = {"config": config}
    session_id: Optional[str] = None

    while True:
        _print_prompt()
        user_input = _read_input()

        # Ctrl-D inside _read_input returns None → exit cleanly.
        if user_input is None:
            sys.stdout.write("\n")
            print_success("Bye.")
            return 0

        if not user_input:
            continue

        # ── slash-command dispatch. Every command family returns either
        #    nothing (mutates state in place) or (None, sentinel) when
        #    we need to break out of the loop.
        cmd, _, arg = user_input.partition(" ")

        if cmd in ("/exit", "/quit", "exit", "quit"):
            print_success("Bye.")
            return 0

        if cmd == "/help":
            show_help(config.get("ai", {}).get("provider", "?"),
                      config.get("ai", {}).get("model", ""))
            continue

        if cmd == "/clear":
            if HAS_RICH:
                console.clear()
            else:
                os.system("cls" if os.name == "nt" else "clear")
            print_banner()
            _reload()
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

        # Default → stream the user prompt to the model.
        try:
            try:
                from src.ai.safety.guard import get_guard
                get_guard().reset()
            except Exception:
                pass
            t0 = time.time()
            text, tool_events = asyncio.run(
                _stream(orch, user_input, session_id=session_id, history_list=history)
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
