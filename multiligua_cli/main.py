"""
MINXG CLI — Multi-language AI orchestration framework v1.0.0

Commands:
    minxg                    Start TUI chat (streaming + tool call visualization)
    minxg docs               Start local docs server and open in browser
    minxg open               Start OpenAI /v1 API server
    minxg setup              Run setup wizard (repeatable)
    minxg model [name]       Configure AI model/provider/key individually
    minxg api <url>          Quick-set API base URL
    minxg key <key>          Quick-set API Key
    minxg lang [code]        Switch display language
    minxg config             View current configuration
    minxg status             View system status
    minxg tools              List available tools
    minxg gateway            Gateway lifecycle management
    minxg update             Check for updates
    minxg ext <sub>          Extension management
    minxg skill <sub>        Skill management
    minxg help               Show help
    minxg --version          Show version
    minxg --list-extensions  List extensions
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import webbrowser
from pathlib import Path
from typing import Dict, List

from multiligua_cli.utils import (
    HAS_RICH,
    Colors,
    colorize,
    console,
    ensure_config,
    get_config_path,
    get_project_root,
    load_config,
    print_banner,
    print_dim,
    print_error,
    print_info,
    print_success,
    set_process_title,
    __version__,
)
from multiligua_cli.i18n import T, set_lang, get_lang, LANGUAGES, LANG_CODES

def _build_cheatsheet() -> str:
    """Generate command cheatsheet — pure English, banner-themed."""
    lines = [
        f"╔══════════════════════════════════════════════════════════════════════╗",
        f"║  MINXG — commands                                                    ║",
        f"╠══════════════════════════════════════════════════════════════════════╣",
        f"║                                                                      ║",
        f"║  minxg                    Start the TUI chat (default)               ║",
        f"║  minxg setup              Run the setup wizard                       ║",
        f"║  minxg config             Show current configuration                 ║",
        f"║  minxg status             Runtime status                             ║",
        f"║  minxg tools              List available tools                       ║",
        f"║  minxg model [name]       Set or view the model                       ║",
        f"║  minxg api <url>          Quick-set API base URL                      ║",
        f"║  minxg key <key>          Quick-set API key                          ║",
        f"║  minxg lang [code]        Switch display language (en only, default) ║",
        f"║  minxg ext list|add|...   Manage extensions (user-installed)         ║",
        f"║  minxg gateway start|stop|status   API gateway lifecycle             ║",
        f"║  minxg doctor             Self-check (config + tools + extensions)   ║",
        f"║  minxg help               Show this cheatsheet                       ║",
        f"║                                                                      ║",
        f"║  Examples:                                                           ║",
        f"║    minxg model gpt-4o              # one-shot set the model          ║",
        f"║    minxg ext add minxg-adb         # enable built-in ADB extension   ║",
        f"║    minxg gateway start --foreground                                        ║",
        f"║                                                                      ║",
        f"╚══════════════════════════════════════════════════════════════════════╝",
    ]
    return "\n".join(lines)

def print_cheatsheet():
    """Print command cheatsheet."""
    sheet = _build_cheatsheet()
    if HAS_RICH:
        from rich.panel import Panel
        from rich import box
        console.print(
            Panel.fit(
                sheet.strip(),
                title=f"[bold green]✓ {T('config_saved')}[/bold green]",
                border_style="green",
                box=box.HEAVY,
            )
        )
    else:
        print(colorize(sheet, Colors.GREEN))

def run_tools(args) -> int:
    """List available tools."""
    try:
        from multiling.model_tools import get_available_toolsets, get_all_tool_names
        from multiling.platform_cap import detect_platform_key, cap_for, summary
        toolsets = get_available_toolsets()
        all_tools = get_all_tool_names()

        ps = summary()
        cap_line = (
            f" platform: {ps['platform']} · "
            f"cap: {ps['cap']} · "
            f"active: {ps['active_count']}/{ps['registered_count']} tools"
        )
        if HAS_RICH:
            console.print()
            console.print(cap_line, style="cyan")
            console.print()

        if HAS_RICH:
            from rich.table import Table
            from rich import box
            table = Table(title=f"[Tools] {T('tools_title')}", box=box.ROUNDED)
            table.add_column("Status", style="green", width=4)
            table.add_column(T("cfg_ai_provider"), style="cyan")
            table.add_column(T("status_extensions"), style="white")
            table.add_column("Tools", style="dim")
            for ts_name, ts_data in sorted(toolsets.items()):
                status = "✓" if ts_data.get("available", False) else "✗"
                tool_names = ", ".join(ts_data.get("tools", [])[:6])
                if len(ts_data.get("tools", [])) > 6:
                    tool_names += f" ... +{len(ts_data.get('tools', [])) - 6}"
                style = "green" if ts_data.get("available") else "red"
                table.add_row(
                    f"[{style}]{status}[/{style}]",
                    ts_name,
                    str(len(ts_data.get("tools", []))),
                    tool_names,
                )
            console.print(table)
            console.print(
                f"\n[dim]{T('tools_total', total=len(all_tools), sets=len(toolsets))}[/dim]"
            )
        else:
            print(colorize(f"\n[Tools] {T('tools_title')}:", Colors.CYAN, Colors.BOLD))
            print(cap_line)
            for ts_name, ts_data in sorted(toolsets.items()):
                status = "OK " if ts_data.get("available", False) else "FAIL"
                n = len(ts_data.get("tools", []))
                print(f"  {status} {ts_name}: {n} tools")
            print(
                colorize(
                    f"\n{T('tools_total', total=len(all_tools), sets=len(toolsets))}",
                    Colors.DIM,
                )
            )
        return 0
    except Exception as e:
        print_error(T("tools_list_failed", error=str(e)))
        return 1

def run_config_show(args) -> int:
    """Show current configuration."""
    config = load_config()

    if HAS_RICH:
        from rich.table import Table
        from rich import box
        table = Table(title="[Config] Current Configuration", box=box.ROUNDED)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        ai = config.get("ai", {})
        table.add_row(f"[bold]{T('cfg_ai_provider')}[/bold]", ai.get("provider", T("cfg_not_set")))
        table.add_row(f"[bold]{T('cfg_model')}[/bold]", ai.get("model", T("cfg_not_set")))
        table.add_row(f"[bold]{T('cfg_api_url')}[/bold]", ai.get("base_url", T("cfg_not_set")))
        key_val = ai.get("api_key", "")
        table.add_row(
            f"[bold]{T('cfg_api_key')}[/bold]",
            ("***" + key_val[-4:]) if key_val else T("cfg_not_set"),
        )
        table.add_row(f"[bold]{T('cfg_temperature')}[/bold]", str(ai.get("temperature", 0.3)))
        table.add_row(f"[bold]{T('cfg_max_tokens')}[/bold]", str(ai.get("max_tokens", "default")))
        table.add_row(f"[bold]{T('cfg_concurrency')}[/bold]", str(ai.get("concurrency", "default")))
        table.add_row(f"[bold]{T('cfg_max_tool_calls')}[/bold]", str(ai.get("max_tool_calls", "default")))

        gw = config.get("gateway", {})
        table.add_row(f"[bold]{T('cfg_gateway_port')}[/bold]", str(gw.get("port", 18080)))
        table.add_row(f"[bold]{T('cfg_gateway_key')}[/bold]", T("cfg_set") if gw.get("api_key") else T("cfg_not_set"))

        wk = config.get("workers", {})
        table.add_row(f"[bold]{T('cfg_workers_port')}[/bold]", str(wk.get("port", 19001)))

        lang = config.get("lang", "en")
        lang_info = LANGUAGES.get(lang, {})
        table.add_row("[bold]Language[/bold]", lang_info.get("native", lang))

        console.print(table)
    else:
        print(colorize("\n[Config] Current Configuration:", Colors.CYAN, Colors.BOLD))
        ai = config.get("ai", {})
        print(f"  {T('cfg_ai_provider')}: {ai.get('provider', T('cfg_not_set'))}")
        print(f"  {T('cfg_model')}: {ai.get('model', T('cfg_not_set'))}")
        print(f"  {T('cfg_api_url')}: {ai.get('base_url', T('cfg_not_set'))}")
        key_val = ai.get("api_key", "")
        key_display = ("***" + key_val[-4:]) if key_val else T("cfg_not_set")
        print(f"  {T('cfg_api_key')}: {key_display}")
    return 0

def run_status(args) -> int:
    """Show system status."""
    config = load_config()
    has_config = bool(config)

    if HAS_RICH:
        from rich.table import Table
        from rich import box
        table = Table(title="System Status", box=box.ROUNDED)
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="white")
        table.add_row("[bold]Config[/bold]",
            "[green]Found[/green]" if has_config else "[red]Missing[/red]")
        table.add_row("[bold]Version[/bold]", __version__)
        table.add_row("[bold]Python[/bold]", sys.version.split()[0])
        table.add_row("[bold]Platform[/bold]", sys.platform)
        if has_config:
            ai = config.get("ai", {})
            table.add_row("[bold]AI Provider[/bold]", ai.get("provider", "Not set"))
            table.add_row("[bold]Model[/bold]", ai.get("model", "Not set"))
            table.add_row("[bold]Language[/bold]", "English")
        console.print(table)
    else:
        print(colorize("\nSystem Status", Colors.CYAN, Colors.BOLD))
        print(f"  Config: {'Found' if has_config else 'Missing'}")
        print(f"  Version: {__version__}")
        print(f"  Python: {sys.version.split()[0]}")
        print(f"  Platform: {sys.platform}")
        if has_config:
            ai = config.get("ai", {})
            print(f"  AI Provider: {ai.get('provider', 'Not set')}")
            print(f"  Model: {ai.get('model', 'Not set')}")
    return 0

@ensure_config
def run_open(args) -> int:
    """Start OpenAI /v1 API server."""
    from multiling.orchestrator import start_api_server
    config = load_config()
    port = args.port or config.get("gateway", {}).get("port", 18080)
    host = args.host or "0.0.0.0"
    api_key = args.api_key or config.get("gateway", {}).get("api_key")

    if not api_key:
        import secrets
        api_key = secrets.token_hex(16)
        print_info(f"Generated API key: {api_key[:16]}...")

    if HAS_RICH:
        from rich.panel import Panel
        from rich import box
        console.print(Panel.fit(
            f"[bold cyan]MINXG OpenAPI Server[/bold cyan]\n\n"
            f"  Address: [green]http://{host}:{port}[/green]\n"
            f"  Endpoint: [green]http://{host}:{port}/v1/chat/completions[/green]\n"
            f"  Key: [dim]{api_key[:16]}...[/dim]\n\n"
            f"[dim]Press Ctrl+C to stop[/dim]",
            title="MINXG Open", border_style="cyan", box=box.HEAVY,
        ))
    else:
        print(colorize(f"\nMINXG OpenAPI Server", Colors.CYAN, Colors.BOLD))
        print(f"  Address: http://{host}:{port}")
        print(colorize(f"\nPress Ctrl+C to stop", Colors.DIM))

    asyncio.run(
        start_api_server(
            host=host, port=port, api_key=api_key,
            ai_base_url=config.get("ai", {}).get("base_url"),
            ai_api_key=config.get("ai", {}).get("api_key"),
            ai_provider=config.get("ai", {}).get("provider", "openai"),
            ai_model=config.get("ai", {}).get("model"),
        )
    )
    return 0

@ensure_config
def run_docs(args) -> int:
    """Start local documentation server."""
    import http.server
    import socketserver

    docs_dir = get_project_root() / "docs"
    if not docs_dir.exists():
        print_error("docs/ directory not found")
        return 1

    port = args.port or 8080
    os.chdir(docs_dir)
    url = f"http://localhost:{port}/"
    try:
        webbrowser.open(url)
    except Exception:
        pass

    if HAS_RICH:
        from rich.panel import Panel
        from rich import box
        console.print(Panel.fit(
            f"[bold green]MINXG Documentation[/bold green]\n\n"
            f"  Home: [cyan underline]{url}[/cyan underline]\n"
            f"  User Guide: [dim underline]{url}guide.html[/dim underline]\n"
            f"  API Reference: [dim underline]{url}api.html[/dim underline]\n\n"
            f"[dim]Press Ctrl+C to stop[/dim]",
            border_style="green", box=box.HEAVY,
        ))
    else:
        print(colorize(f"\nMINXG Documentation", Colors.GREEN, Colors.BOLD))
        print(colorize(f"  Home: {url}", Colors.CYAN))

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()
    return 0

def run_model_config(args) -> int:
    """Configure AI model. Supports: minxg model or minxg model <name>."""
    model_arg = getattr(args, "model_name", None)
    if model_arg:

        config = load_config()
        config.setdefault("ai", {})["model"] = model_arg

        import yaml
        cfg_path = get_config_path()
        with open(cfg_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print_success(T("shortcut_model_done", model=model_arg))
        return 0

    from multiligua_cli.setup import run_setup
    print_banner()
    return run_setup()

def run_api_config(args) -> int:
    """Quick-set API base URL: minxg api <url>."""
    url = args.url
    config = load_config()
    config.setdefault("ai", {})["base_url"] = url

    import yaml
    cfg_path = get_config_path()
    with open(cfg_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print_success(T("shortcut_api_done", url=url))
    return 0

def run_key_config(args) -> int:
    """Quick-set API Key: minxg key <key>."""
    key = args.apikey
    config = load_config()
    config.setdefault("ai", {})["api_key"] = key

    import yaml
    cfg_path = get_config_path()
    with open(cfg_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print_success(T("shortcut_key_done"))
    return 0

def run_lang_config(args) -> int:
    """Switch language: minxg lang [code] or minxg lang (interactive)."""
    code_arg = getattr(args, "lang_code", None)

    if code_arg:
        if code_arg not in LANGUAGES:
            print_error(f"Unknown language code: {code_arg}")
            print_info(f"Available: {', '.join(LANG_CODES)}")
            return 1
        new_lang = code_arg
    else:

        new_lang = _lang_tui_selector()
        if new_lang is None:
            return 1

    set_lang(new_lang)
    info = LANGUAGES[new_lang]

    config = load_config()
    config["lang"] = new_lang
    import yaml
    cfg_path = get_config_path()
    with open(cfg_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print_success(T("lang_switched", name=info["native"]))
    return 0

def _lang_tui_selector() -> str | None:
    """Language TUI selector."""
    from multiligua_cli.wizard_ui import MinxgMenu
    current = get_lang()

    options = []
    descriptions = []
    for code, info in LANGUAGES.items():
        marker = " ◀" if code == current else ""
        options.append(f"{info['native']} ({info['name']}){marker}")
        descriptions.append(f"  Code: {code}")

    menu = MinxgMenu(T("step_language"), options, descriptions)
    result = menu.run()
    if result is None:
        return None

    return list(LANGUAGES.keys())[result]

def cmd_setup(args) -> int:
    """Run the full setup wizard (dispatched from main())."""
    from multiligua_cli.setup import run_setup as setup_main
    # setup.py prints the rich banner itself — don't double up.
    result = setup_main()
    if result == 0:
        print_cheatsheet()
    return result

CORE_COMMANDS = frozenset({
    "docs", "open", "setup", "model", "api", "key", "lang",
    "config", "status", "tools", "gateway", "update", "ext", "skill", "help",
})

def _print_completion_hint() -> None:
    """Show the post-install / first-run cheatsheet."""
    try:
        sys.stdout.write("\n")
        sys.stdout.write(_build_cheatsheet())
        sys.stdout.write("\n  Type `minxg` to start the TUI chat.\n\n")
        sys.stdout.flush()
    except Exception:
        pass

def main(argv=None) -> int:
    """Route to subcommands. No args drops into the TUI chat.

    Subcommands that auto-loaded behaviour (start, adb, root, files,
    update, skill) have been removed in this build:
      - `start` was an alias that conflated TUI with the gateway.
      - `adb` / `root` / `files` are extensions; enable them with
        `minxg ext add minxg-adb` etc.
      - `update` was the removed hot-reload path.
      - `skill` is in flux; inside the TUI, use `/help` for the
        command index and `minxg doctor` for diagnostic output.
    """
    set_process_title()

    parser = argparse.ArgumentParser(
        prog="minxg",
        description="MINXG — five-pillar worker platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Core commands:
  minxg                   Start the TUI chat (default)
  minxg setup             Run the setup wizard
  minxg config            Show current configuration
  minxg status            Show runtime status
  minxg tools             List available tools
  minxg model [NAME]      Set or view the active model
  minxg api <URL>         Quick-set the API base URL
  minxg key <KEY>         Quick-set the API key
  minxg ext ...           Manage user-installed extensions
  minxg gateway ...       API gateway lifecycle (start | stop | status)
  minxg doctor            Self-check (config + tools + extensions)
  minxg --version         Show version

Examples:
  minxg
  minxg model gpt-4o
  minxg ext add minxg-adb
  minxg gateway start --foreground
""",
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging")
    parser.add_argument("--list-extensions", action="store_true",
                        help="List all extensions and exit")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("setup", help="Run the setup wizard")
    sub.add_parser("config", help="Show current configuration")
    sub.add_parser("status", help="Show runtime status")
    sub.add_parser("tools", help="List available tools")
    sub.add_parser("help", help="Show command cheatsheet")

    p_model = sub.add_parser("model", help="Set or view the active model")
    p_model.add_argument("model_name", nargs="?",
                         help="Model name (optional; omit to view)")

    p_api = sub.add_parser("api", help="Quick-set the API base URL")
    p_api.add_argument("url", help="API base URL")

    p_key = sub.add_parser("key", help="Quick-set the API key")
    p_key.add_argument("apikey", help="API key")

    p_lang = sub.add_parser("lang",
                             help="Switch display language (English-only)")
    p_lang.add_argument("lang_code", nargs="?",
                        help=f"Language code ({', '.join(LANG_CODES[:3])}...)")

    p_gw = sub.add_parser("gateway",
                          help="API gateway lifecycle (start | stop | status)")
    p_gw.add_argument("sub_command", nargs="?",
                      choices=["start", "stop", "status"],
                      help="Sub-command to run")

    p_doctor = sub.add_parser("doctor",
                               help="Self-check (config + tools + extensions)")

    p_ext = sub.add_parser("ext", help="Manage user-installed extensions")
    ext_sub = p_ext.add_subparsers(dest="ext_action", metavar="<action>")
    ext_sub.add_parser("list", help="List installed extensions")
    ext_sub.add_parser("available",
                        help="List built-in optional extensions")
    p_ext_add = ext_sub.add_parser(
        "add", help="Install a built-in slug or path/to/pkg.py")
    p_ext_add.add_argument("spec", nargs="+",
                           help="Extension slug or path")
    p_ext_rm = ext_sub.add_parser("remove",
                                   help="Remove an installed extension")
    p_ext_rm.add_argument("name", help="Extension name to remove")
    p_ext_info = ext_sub.add_parser("info",
                                     help="Show details of one extension")
    p_ext_info.add_argument("name", help="Extension name")
    p_ext_enable = ext_sub.add_parser(
        "enable", help="Enable without re-installing")
    p_ext_enable.add_argument("name", help="Extension name")
    p_ext_disable = ext_sub.add_parser(
        "disable", help="Disable without removing")
    p_ext_disable.add_argument("name", help="Extension name")

    args = parser.parse_args(argv)

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.INFO)
        os.environ["MINXG_LOG_LEVEL"] = "INFO"

    if getattr(args, "list_extensions", False):
        try:
            from extensions import list_extensions
            rows = []
            for e in list_extensions():
                rows.append((e["name"], e["source"], str(e["priority"]),
                             e["description"]))
            if not rows:
                print_info("No extensions registered.")
            else:
                for name, src, prio, desc in rows:
                    print(f"  {name:24s} {src:10s} p={prio:>3s}  {desc}")
        except Exception as e:
            print_warning(f"extension list failed: {e}")
        return 0

    cmd = getattr(args, "command", None)

    if cmd == "help":
        sys.stdout.write(_build_cheatsheet() + "\n")
        sys.stdout.flush()
        return 0

    if cmd == "setup":
        rc = cmd_setup(args)
        if rc == 0:
            _print_completion_hint()
        return rc

    if cmd == "config":
        return run_config_show(args)
    if cmd == "status":
        return run_status(args)
    if cmd == "tools":
        return run_tools(args)
    if cmd == "model":
        return run_model_config(args)
    if cmd == "api":
        return run_api_config(args)
    if cmd == "key":
        return run_key_config(args)
    if cmd == "lang":
        return run_lang_config(args)

    if cmd == "gateway":
        sub_c = getattr(args, "sub_command", None) or "status"
        from multiligua_cli.gateway_cli import (
            gateway_foreground, gateway_start, gateway_stop, gateway_status,
        )
        if sub_c == "start":
            return gateway_start(args)
        if sub_c == "stop":
            return gateway_stop(args)
        return gateway_status(args)

    if cmd == "doctor":
        from multiligua_cli.doctor import run_doctor
        return run_doctor(args)

    if cmd == "ext":
        ext_act = getattr(args, "ext_action", None)
        from extensions.package_cli import dispatch_ext_command
        return dispatch_ext_command(args, ext_act)

    # No subcommand -> ask: chat CLI or start API gateway?
    mode = _pick_initial_mode()
    if mode == "gateway":
        from multiligua_cli.gateway_cli import gateway_start
        return gateway_start(args)
    if mode == "setup":
        from multiligua_cli.setup import run_setup
        rc = run_setup()
        if rc == 0:
            _print_completion_hint()
        return rc
    from multiligua_cli.tui_chat import tui_chat
    return tui_chat(args)


def _pick_initial_mode() -> str:
    """One-shot picker for `minxg` with no subcommand.

    Lets the user choose between starting the chat CLI immediately
    or starting an OpenAI-compatible v1 gateway endpoint. Returns
    'chat' on any non-interactive / EOF / auto-pick default.
    """
    try:
        from multiligua_cli.utils import HAS_RICH, console, Colors
        from multiligua_cli.wizard_ui import (
            print_chat_banner, print_section, prompt_choice,
        )
        print_chat_banner()
        print_section("What do you want to do?")
        choices = [
            f"{chr(0x1F4AC)} Chat CLI",
            f"{chr(0x1F310)} Start API gateway",
            f"{chr(0x2699)}{chr(0xFE0F)} Run setup wizard",
        ]
        descs = [
            "talk to the model directly",
            "expose an OpenAI-compatible v1 endpoint",
            "change language, provider, model, reasoning, gateway",
        ]
        idx = prompt_choice("Pick a starting mode",
                            choices, descs, default=0)
        return ("chat", "gateway", "setup")[idx]
    except (KeyboardInterrupt, EOFError):
        print()
        return "chat"
    except Exception:
        return "chat"

if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
