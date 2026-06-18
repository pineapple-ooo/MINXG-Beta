"""

  - setup.py only orchestrates flow; all text is English
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional


from multiligua_cli.i18n import T, set_lang, get_lang, LANGUAGES, LANG_NAMES, LANG_CODES

from multiligua_cli.wizard_ui import (
    clear_screen, print_banner, print_step_progress,
    print_success, print_error, print_info, print_warning,
    print_section, print_kv, print_option_item,
    MinxgMenu, prompt, prompt_yes_no, prompt_choice,
    Colors, HAS_RICH, console,
)

__version__ = "0.0.0+unknown"
try:
    from minxg import VERSION as __version__
except Exception:
    pass






def _project_root() -> Path:
    return Path(__file__).parent.parent.resolve()

def _config_path() -> Path:
    return _project_root() / "config.yaml"

def _env_path() -> Path:
    return _project_root() / ".env"






def load_existing_config() -> Dict[str, Any]:
    config_path = _config_path()
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config:
                    return config
        except Exception as e:
            print_warning(f"Save failed: {e}")
    return {}


def save_config(config: Dict[str, Any]) -> None:
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print_success("Config saved")


def save_env(key: str, value: str) -> None:
    """Save a key=value pair to the .env file, preserving existing entries."""
    env_path = _env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_vars: dict[str, str] = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env_vars[k] = v
    env_vars[key] = value
    with open(env_path, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")





from multiligua_cli.providers import AI_PROVIDERS




from multiligua_cli.platforms import PLATFORMS, PLATFORM_ORDER






TOTAL_STEPS = 8


def setup_language(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 1: Language — hardcoded to English."""
    print_step_progress(1, TOTAL_STEPS, "Language")

    config["lang"] = "en"
    print_success("Language: English")


def setup_ai_provider(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    print_step_progress(2, TOTAL_STEPS, "AI Provider")

    provider_names = [f"{p['emoji']} {p['name']}" for p in AI_PROVIDERS.values()]
    provider_descriptions = [p["description"] for p in AI_PROVIDERS.values()]

    existing_provider = existing.get("ai", {}).get("provider")
    default_idx = 0
    if existing_provider and existing_provider in AI_PROVIDERS:
        provider_keys = list(AI_PROVIDERS.keys())
        if existing_provider in provider_keys:
            default_idx = provider_keys.index(existing_provider)

    selected = prompt_choice("Select AI provider", provider_names, provider_descriptions, default_idx)
    provider_key = list(AI_PROVIDERS.keys())[selected]
    provider_info = AI_PROVIDERS[provider_key]

    config["ai"] = config.get("ai", {})
    config["ai"]["provider"] = provider_key
    print_success("Provider configured" + f" — {provider_info['name']}")

    if provider_key == "local":
        print_info("Local mode: set base_url to your server endpoint")
        config["ai"]["model"] = ""
        config["ai"]["base_url"] = ""
        config["ai"]["api_key"] = ""
        return

    print_section("API URL")
    base_url = prompt(
        "Enter API URL (or press Enter to skip)",
        existing.get("ai", {}).get("base_url") or provider_info["default_url"]
    )
    config["ai"]["base_url"] = base_url
    print_success("API URL configured")


    if provider_info["needs_api_key"]:
        print_section("API Key")
        existing_key = existing.get("ai", {}).get("api_key", "")
        key_hint = ("***" + existing_key[-4:]) if existing_key else ""
        api_key = prompt("Enter API key", key_hint, password=True)
        config["ai"]["api_key"] = api_key
        print_success("API key configured")

    print_section("Model Selection")
    model = _prompt_model_with_fetch(
        provider_info, existing.get("ai", {}).get("model"), base_url,
        config["ai"].get("api_key", ""),
    )
    config["ai"]["model"] = model
    print_success("Model configured" + f" — {model}")

    print_section("Environment")
    existing_mt = existing.get("ai", {}).get("max_tokens")
    max_tok = prompt("Max tokens", str(existing_mt or 0))
    config["ai"]["max_tokens"] = int(max_tok) if max_tok and int(max_tok) > 0 else 0

    existing_cc = existing.get("ai", {}).get("concurrency")
    cc = prompt("Max concurrency", str(existing_cc or 1))
    config["ai"]["concurrency"] = int(cc) if cc else 1

    existing_mtc = existing.get("ai", {}).get("max_tool_calls")
    mtc = prompt("Max tool calls per round", str(existing_mtc or 0))
    config["ai"]["max_tool_calls"] = int(mtc) if mtc else 0

    existing_temp = existing.get("ai", {}).get("temperature", 0.3)
    temp = prompt("Temperature", str(existing_temp))
    config["ai"]["temperature"] = float(temp) if temp else 0.3

    print_success("Provider configured")


def _prompt_model_with_fetch(provider_info: dict, existing_model: str | None,
                              base_url: str, api_key: str) -> str:
    default_model = existing_model or provider_info["default_model"]
    fetched_models = _fetch_models(base_url, api_key)

    if fetched_models:
        print_info("Fetched models from provider")
        for i, m in enumerate(fetched_models[:20]):
            print(f"  {i + 1:2d}. {m}")
        if len(fetched_models) > 20:
            print_info("More models available")
    else:
        print_warning("Could not fetch models")

    return prompt("Enter model name", default_model)


def _fetch_models(base_url: str, api_key: str) -> List[str]:
    """Fetch available models from the provider's /models endpoint.
    Uses TLS with certificate verification; falls back gracefully."""
    import ssl
    try:
        import urllib.request
        url = base_url.rstrip("/") + "/models"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, dict):
                models = data.get("data", data.get("models", []))
                if not models:
                    return []
                names = []
                for m in models:
                    n = m.get("id", m.get("name", "")) if isinstance(m, dict) else str(m)
                    if n:
                        names.append(n)
                return names[:50]
    except Exception:
        pass
    return []


def setup_platforms(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    print_step_progress(3, TOTAL_STEPS, "Platforms")
    print_info("Select platforms to enable:")

    platforms = {}
    existing_platforms = existing.get("platforms", {})

    for key in PLATFORM_ORDER:
        pinfo = PLATFORMS[key]
        print_section(f"{pinfo['emoji']} {pinfo['name']} — {pinfo['description']}")

        enable = prompt_yes_no(f"Enable {pinfo['name']}?",
                               default=(key in existing_platforms))
        if not enable:
            continue

        plat_config = {}
        for field in pinfo["fields"]:
            default_val = existing_platforms.get(key, {}).get(field["name"], "")
            val = prompt(
                f"    {field['label']}",
                default_val,
                password=field.get("password", False)
            )
            if val:
                plat_config[field["name"]] = val

        if plat_config:
            platforms[key] = plat_config
            print_success(f"{pinfo['name']} ✓")

    config["platforms"] = platforms
    print_success("Platforms configured")


def setup_gateway(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    print_step_progress(4, TOTAL_STEPS, "Gateway")

    existing_gw = existing.get("gateway", {})

    host = prompt("Gateway host", existing_gw.get("host", "0.0.0.0"))
    port = prompt("Gateway port", str(existing_gw.get("port", 19001)))

    config["gateway"] = {
        "host": host,
        "port": int(port) if port.isdigit() else 19001,
    }

    auto = prompt_yes_no("Auto-start gateway on launch?", default=existing_gw.get("auto_start", False))
    config["gateway"]["auto_start"] = auto

    print_success("Gateway configured")


def setup_environment(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    print_step_progress(5, TOTAL_STEPS, "Environment")

    existing_env = existing.get("environment", {})

    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    log_descs = [
        "Debug (all messages)",
        "Info (normal operation)",
        "Warning",
        "Error only",
    ]
    existing_log = existing_env.get("log_level", "INFO")
    log_idx = log_levels.index(existing_log) if existing_log in log_levels else 1
    selected_log = prompt_choice("Log level", log_levels, log_descs, default=log_idx)

    debug = prompt_yes_no("Enable debug mode?", default=existing_env.get("debug", False))

    workers_port = prompt("Workers RPC port", str(existing_env.get("workers_port", 19001)))

    workers_autostart = prompt_yes_no("Auto-start workers on launch?", default=existing_env.get("workers_autostart", True))

    health_interval = prompt("Health check interval (seconds)", str(existing_env.get("health_check_interval", 60)))

    print_section("Performance Optimization")
    print_info("Mobile optimization reduces memory/CPU usage")
    existing_perf = existing.get("perf", {})
    mobile_opt = prompt_yes_no("Performance Optimization", default=existing_perf.get("mobile_optimization", True))
    config["perf"] = {"mobile_optimization": mobile_opt}
    if mobile_opt:
        print_success("Mobile optimization enabled")
    else:
        print_warning("Mobile optimization disabled")

    config["environment"] = {
        "log_level": log_levels[selected_log],
        "debug": debug,
        "workers_port": int(workers_port) if workers_port.isdigit() else 19001,
        "workers_autostart": workers_autostart,
        "health_check_interval": int(health_interval) if health_interval.isdigit() else 60,
    }

    print_success("Environment configured")


def setup_hot_reload(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    config["hot_reload"] = {"enabled": False}
    print_info("Hot-reload has been removed in this build.")


def setup_browser_search(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 7: Browser search configuration."""
    print_step_progress(7, TOTAL_STEPS, "Browser Search")

    existing_bs = existing.get("browser_search", {})

    enabled = prompt_yes_no("Enable browser search for AI", default=existing_bs.get("enabled", False))
    if not enabled:
        config["browser_search"] = {"enabled": False}
        print_info("Browser search disabled")
        return

    print_section("API Configuration")
    api_types = ["User's own browser", "Custom AI search API"]
    api_type_idx = 0 if existing_bs.get("api_type") == "user" else 1

    selected_api = prompt_choice("Search method", api_types, ["Use system browser", "Use AI search API endpoint"], default=api_type_idx)
    api_type = "user" if selected_api == 0 else "api"

    config["browser_search"] = {"enabled": True, "api_type": api_type}

    if api_type == "api":
        api_url = prompt("API URL", existing_bs.get("api_url", ""))
        config["browser_search"]["api_url"] = api_url

        api_key = prompt("API Key", existing_bs.get("api_key", ""), password=True)
        if api_key:
            config["browser_search"]["api_key"] = api_key

        model = prompt("Model (optional)", existing_bs.get("model", ""))
        if model:
            config["browser_search"]["model"] = model

    print_success("Browser search configured")


def show_summary(config: Dict[str, Any]) -> None:
    """Step 8: Configuration summary + save."""
    print_step_progress(8, TOTAL_STEPS, "Summary & Save")
    print()

    lang = config.get("lang", "en")
    print_kv("Language", lang)

    ai = config.get("ai", {})
    print_kv("Provider", ai.get("provider", "—"))
    print_kv("Model", ai.get("model", "—"))
    print_kv("API URL", ai.get("base_url", "—"))
    if ai.get("max_tokens"):
        print_kv("Max Tokens", str(ai["max_tokens"]))
    if ai.get("temperature") is not None:
        print_kv("Temperature", str(ai["temperature"]))

    platforms = config.get("platforms", {})
    if platforms:
        print_kv("Platforms", f"{len(platforms)} enabled")
        for k in platforms:
            pinfo = PLATFORMS.get(k, {})
            print_kv(f"  {pinfo.get('name', k)}", "enabled", indent=6)
    else:
        print_kv("Platforms", "none")

    gw = config.get("gateway", {})
    print_kv("Gateway", f"{gw.get('host', '0.0.0.0')}:{gw.get('port', 19001)}")

    env = config.get("environment", {})
    env_str = f"{env.get('log_level', 'INFO')} | debug={env.get('debug', False)}"
    print_kv("Environment", env_str)

    perf = config.get("perf", {})
    perf_str = "enabled" if perf.get("mobile_optimization", True) else "disabled"
    print_kv("Performance", perf_str)

    bs = config.get("browser_search", {})
    if bs.get("enabled"):
        api_type = bs.get("api_type", "user")
        print_kv("Browser Search", f"enabled ({api_type})")
    else:
        print_kv("Browser Search", "disabled")

    print()


def run_setup():
    """Main wizard entry."""
    clear_screen()
    print_banner()

    existing = load_existing_config()
    if existing:
        print_info("Found existing config, will prompt for changes.")

    config = {}

    setup_language(config, existing)

    setup_ai_provider(config, existing)
    setup_platforms(config, existing)
    setup_gateway(config, existing)
    setup_environment(config, existing)
    setup_hot_reload(config, existing)

    setup_browser_search(config, existing)

    show_summary(config)

    if prompt_yes_no("Save configuration?", default=True):
        save_config(config)
        if config.get("ai", {}).get("api_key"):
            save_env("AI_API_KEY", config["ai"]["api_key"])
        _post_setup_hints(config)
    else:
        print_info("Setup cancelled.")
    
    print()
    print_success("Goodbye!")


def _post_setup_hints(config: Dict[str, Any]) -> None:
    """Post-setup hints."""
    print()
    if HAS_RICH:
        from rich.panel import Panel
        console.print(Panel.fit(
            "  Setup complete!\n"
            "  Start: [bold]minxg start[/bold]\n"
            "  Docs: [bold]minxg docs[/bold]\n"
            "  Help: [bold]minxg --help[/bold]\n"
            "  Reconfigure: [bold]minxg setup[/bold]",
            title="MINXG", border_style="gold3"
        ))
    else:
        from multiligua_cli.wizard_ui import Colors, _ansi
        print(_ansi("╔══════════════════════════════════════╗", Colors.GOLD))
        print(_ansi(f"║  Setup complete!                    ║", Colors.GOLD, Colors.BOLD))
        print(_ansi(f"║  Start:   minxg start                ║", Colors.INDIGO))
        print(_ansi(f"║  Docs:    minxg docs                 ║", Colors.TEAL))
        print(_ansi(f"║  Help:    minxg --help               ║", Colors.SLATE))
        print(_ansi(f"║  Config:  minxg setup                ║", Colors.AMETHYST))
        print(_ansi("╚══════════════════════════════════════╝", Colors.GOLD))
    print()


if __name__ == "__main__":
    run_setup()
