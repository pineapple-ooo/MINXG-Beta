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
    """Generate command cheatsheet based on current language."""
    lang = get_lang()
    flag = get_lang_flag(lang)
    lines = [
        f"╔══════════════════════════════════════════════════════════════════════╗",
        f"║               [ Cheatsheet ] {T('cheatsheet_title')}                          ║",
        f"╠══════════════════════════════════════════════════════════════════════╣",
        f"║                                                                      ║",
        f"║   minxg              {T('cmd_minxg')}",
        f"║   minxg docs         {T('cmd_docs')}",
        f"║   minxg open         {T('cmd_open')}",
        f"║   minxg setup        {T('cmd_setup')}",
        f"║   minxg model [name] {T('cmd_model')}",
        f"║   minxg api <url>    {T('cmd_api')}",
        f"║   minxg key <key>    {T('cmd_key')}",
        f"║   minxg lang [code]  {T('cmd_lang')}",
        f"║   minxg config       {T('cmd_config')}",
        f"║   minxg status       {T('cmd_status')}",
        f"║   minxg tools        {T('cmd_tools')}",
        f"║   minxg gateway      {T('cmd_gateway')}",
        f"║   minxg update       {T('cmd_update')}",
        f"║   minxg ext          {T('cmd_ext')}",
        f"║   minxg skill        {T('cmd_skill')}",
        f"║   minxg help         {T('cmd_help')}",
        f"║                                                                      ║",
        f"║   {T('cheatsheet_hint')}",
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
        toolsets = get_available_toolsets()
        all_tools = get_all_tool_names()

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


@ensure_config
def run_setup(args) -> int:
    """Run the full setup wizard."""
    from multiligua_cli.setup import run_setup as setup_main
    print_banner()
    result = setup_main()
    if result == 0:
        print_cheatsheet()
    return result






CORE_COMMANDS = frozenset({
    "docs", "open", "setup", "model", "api", "key", "lang",
    "config", "status", "tools", "gateway", "update", "ext", "skill", "help",
})






def main(argv: List[str] = None) -> int:
    """Route to subcommands. No args defaults to TUI chat."""
    set_process_title()

    parser = argparse.ArgumentParser(
        description="MINXG — Multi-Language AI Orchestration Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
Core Commands:
  minxg                    {T('cmd_minxg')}
  minxg docs               {T('cmd_docs')}
  minxg open               {T('cmd_open')}
  minxg setup              {T('cmd_setup')}
  minxg model [name]       {T('cmd_model')}
  minxg api <url>          {T('cmd_api')}
  minxg key <key>          {T('cmd_key')}
  minxg lang [code]        {T('cmd_lang')}
  minxg config             {T('cmd_config')}
  minxg status             {T('cmd_status')}
  minxg tools              {T('cmd_tools')}
  minxg gateway            {T('cmd_gateway')}
  minxg update             {T('cmd_update')}
  minxg ext                {T('cmd_ext')}
  minxg skill              {T('cmd_skill')}
  minxg help               {T('cmd_help')}

Examples:
  minxg                          # Start TUI chat
  minxg model gpt-4o             # Quick-set model
  minxg api https://api.x.com/v1 # Quick-set API URL
  minxg key sk-xxxx              # Quick-set API key
  minxg lang en                  # Switch to English
  minxg lang                     # Interactive language picker
  minxg docs                     # Open docs in browser
  minxg setup                    # Re-run setup wizard
""",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--list-extensions", action="store_true", help="List all extensions")
    parser.add_argument("--list-skills", action="store_true", help="List all skills")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")


    docs_parser = subparsers.add_parser("docs", help=T("cmd_docs"))
    docs_parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")

    open_parser = subparsers.add_parser("open", help=T("cmd_open"))
    open_parser.add_argument("--port", type=int, help="API port (default: 18080)")
    open_parser.add_argument("--host", default="0.0.0.0", help="Listen address")
    open_parser.add_argument("--api-key", help="Gateway auth key")

    subparsers.add_parser("setup", help=T("cmd_setup"))

    model_parser = subparsers.add_parser("model", help=T("cmd_model"))
    model_parser.add_argument("model_name", nargs="?", help="Model name (optional, skips wizard)")

    subparsers.add_parser("config", help=T("cmd_config"))
    subparsers.add_parser("status", help=T("cmd_status"))
    subparsers.add_parser("tools", help=T("cmd_tools"))
    subparsers.add_parser("help", help=T("cmd_help"))


    api_parser = subparsers.add_parser("api", help=T("cmd_api"))
    api_parser.add_argument("url", help="API base URL")


    key_parser = subparsers.add_parser("key", help=T("cmd_key"))
    key_parser.add_argument("apikey", help="API Key")


    lang_parser = subparsers.add_parser("lang", help=T("cmd_lang"))
    lang_parser.add_argument("lang_code", nargs="?", help=f"Language code ({', '.join(LANG_CODES[:6])}...)")


    gw = subparsers.add_parser("gateway", help=T("cmd_gateway"))
    gw.add_argument("sub_command", nargs="?", choices=["start", "stop", "status"],
                    help="Sub-command: start, stop, status")


    # `start` — top-level convenience alias for `gateway start`.
    # Why: setup.py's user-facing banner (and prior minxg versions) advertise
    # `minxg start` as the entry point. Restoring this alias avoids breaking
    # muscle memory and the original install script's quick-start hints.
    start_parser = subparsers.add_parser(
        "start",
        help="Start the MINXG gateway (alias for 'gateway start')",
        description="Convenience alias: 'minxg start' is identical to 'minxg gateway start'.",
    )
    start_parser.add_argument(
        "--foreground", action="store_true",
        help="Run gateway in foreground instead of backgrounded",
    )
    start_parser.add_argument(
        "--port", type=int, default=None,
        help="Override gateway port (default: from config)",
    )


    up = subparsers.add_parser("update", help=T("cmd_update"))
    up.add_argument("--force", action="store_true", help="Force update")
    up.add_argument("--enable", action="store_true", help="Enable hot reload")
    up.add_argument("--disable", action="store_true", help="Disable hot reload")


    ext_cmd = subparsers.add_parser("ext", help=T("cmd_ext"))
    ext_sub = ext_cmd.add_subparsers(dest="ext_action", help="Action")
    ext_sub.add_parser("list", help=T("ext_list_help"))
    ext_sub.add_parser("browse", help=T("ext_browse_help"))
    ext_sub.add_parser("sample", help=T("ext_sample_help"))


    subparsers.add_parser("skill", help=T("cmd_skill"))


    from extensions import register_cli_extensions
    ext_map: Dict = {}
    try:
        from extensions import register_cli_extensions as _rce
        ext_map = _rce(subparsers)
    except Exception as e:
        print_dim(f"(Extension loading skipped: {e})")


    args = parser.parse_args(argv)

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("extensions").setLevel(logging.DEBUG)


    if getattr(args, "list_extensions", False):
        from extensions import list_extensions
        if HAS_RICH:
            from rich.table import Table
            from rich import box
            table = Table(title="[Extensions]", box=box.ROUNDED)
            table.add_column("Name", style="cyan bold")
            table.add_column("Source", style="magenta")
            table.add_column("Priority", style="yellow")
            table.add_column("Description", style="white")
            for e in list_extensions():
                table.add_row(e["name"], e["source"], str(e["priority"]), e["description"])
            console.print(table)
        return 0

    if getattr(args, "list_skills", False):
        print_info("Skills: (query via skills_list)")
        return 0

    cmd = args.command


    if cmd == "docs":
        return run_docs(args)
    if cmd == "open":
        return run_open(args)
    if cmd == "setup":
        return run_setup(args)
    if cmd == "model":
        return run_model_config(args)
    if cmd == "api":
        return run_api_config(args)
    if cmd == "key":
        return run_key_config(args)
    if cmd == "lang":
        return run_lang_config(args)
    if cmd == "config":
        return run_config_show(args)
    if cmd == "status":
        return run_status(args)
    if cmd == "tools":
        return run_tools(args)
    if cmd == "help":
        parser.print_help()
        return 0
    if cmd == "gateway":
        from multiligua_cli.gateway_cli import (
            gateway_foreground, gateway_start, gateway_stop, gateway_status,
        )
        sub = getattr(args, "sub_command", None)
        if sub == "start":
            return gateway_start(args)
        if sub == "stop":
            return gateway_stop(args)
        if sub == "status":
            return gateway_status(args)
        return gateway_foreground(args)
    if cmd == "start":
        # `minxg start` → forward to gateway_start (or foreground variant).
        from multiligua_cli.gateway_cli import gateway_start, gateway_foreground
        if getattr(args, "foreground", False):
            return gateway_foreground(args)
        return gateway_start(args)
    if cmd == "update":
        from multiligua_cli.utils import print_warning
        print_warning("The 'update' subcommand has been removed in this build.")
        return 0
    if cmd == "ext":
        ea = getattr(args, "ext_action", None)
        if ea == "list":
            from multiligua_cli.extensions.tui import quick_list
            quick_list()
            return 0
        if ea == "browse":
            from multiligua_cli.extensions.tui import browse_extensions
            browse_extensions()
            return 0
        if ea == "sample":
            from multiligua_cli.extensions import get_loader
            loader = get_loader()
            info = loader.install_sample()
            if info:
                print_success(f"Sample extension installed: {info.name} v{info.version}")
                print_info(f"Path: {info.path}")
                print_info("View: minxg ext list")
            return 0

        from multiligua_cli.extensions.tui import browse_extensions
        browse_extensions()
        return 0
    if cmd == "skill":
        print_info("Skill management: coming soon")
        return 0


    if cmd and cmd in ext_map:
        from extensions import dispatch_extension
        return dispatch_extension(ext_map, cmd, args)


    from multiligua_cli.tui_chat import tui_chat
    return tui_chat(args)


if __name__ == "__main__":
    exit_code = main()
    try:
        from multiligua_cli.i18n import T
        from multiligua_cli.utils import print_success
        print_success(T("goodbye"))
    except Exception:
        pass
    sys.exit(exit_code)
