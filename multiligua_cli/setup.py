"""
multiligua_cli/setup.py — MINXG Setup Wizard (v0.18.3 shitshow cleanup edition)

Two tiers: **Quick** (3 steps — get shit done fast) and **Full** (8 steps — every damn option).
All menus use simple numbered lists + text input — no flicker, no bullshit.

New in v0.18.3:
- Vision capability configuration (does your model see images or what?)
- Faster quick mode (3 steps instead of 4)
- More detailed full mode (8 steps of configuration heaven)
- Better model capability detection
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from multiligua_cli.i18n import T, set_lang, get_lang, LANGUAGES, LANG_NAMES, LANG_CODES
from multiligua_cli.providers import (
    REASONING_LEVELS, REASONING_BY_PROVIDER, resolve_reasoning_level,
)
from multiligua_cli.wizard_ui import (
    clear_screen,
    print_success, print_error, print_info, print_warning,
    Colors, HAS_RICH, console, _visual_width,
)

__version__ = "0.0.0+unknown"
try:
    from minxg import VERSION as __version__
except Exception:
    pass

from multiligua_cli.providers import AI_PROVIDERS
from multiligua_cli.platforms import PLATFORMS, PLATFORM_ORDER


# ═══════════════════════════════════════════════════════════════════
#  Blue-premium theme constants
# ═══════════════════════════════════════════════════════════════════

_C_BG_DEEP  = "rgb(10,30,80)"
_C_BG_PANEL = "rgb(16,42,105)"
_C_ACCENT   = "bright_cyan"
_C_BLUE_MID = "deep_sky_blue3"
_C_BLUE_DIM = "rgb(45,85,155)"
_C_GOLD     = "gold3"

_A_BG_DEEP  = "\033[48;5;17m"
_A_BG_PANEL = "\033[48;5;18m"
_A_BLUE     = "\033[38;5;75m"
_A_CYAN     = "\033[38;5;51m"
_A_DIM_BLUE = "\033[38;5;60m"
_A_GOLD     = "\033[38;5;220m"
_A_BOLD     = "\033[1m"
_A_DIM      = "\033[2m"
_A_RESET    = "\033[0m"

TOTAL_STEPS_QUICK = 3
TOTAL_STEPS_FULL = 8


try:
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.console import Group
    from rich import box
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════
#  Model capability detection
# ═══════════════════════════════════════════════════════════════════

# Models that support vision (image understanding)
VISION_CAPABLE_MODELS = {
    # OpenAI
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision-preview",
    "gpt-4", "gpt-3.5-turbo",
    # Anthropic
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "claude-3-5-opus", "claude-3-5-sonnet", "claude-3-5-haiku",
    "claude-sonnet-4", "claude-opus-4",
    # Google
    "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b",
    "gemini-pro-vision",
    # DeepSeek
    "deepseek-vl", "deepseek-vision",
    # Other vision models
    "llava", "llama-3.2-vision", "qwen-vl", "yi-vl",
}

# Models that support function calling
FUNCTION_CALLING_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "claude-3-5-opus", "claude-3-5-sonnet", "claude-3-5-haiku",
    "gemini-1.5-pro", "gemini-1.5-flash",
}

# Models that support streaming
STREAMING_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "claude-3-5-opus", "claude-3-5-sonnet", "claude-3-5-haiku",
    "gemini-1.5-pro", "gemini-1.5-flash",
    "deepseek-chat", "deepseek-coder",
}


def detect_model_capabilities(model_name: str) -> Dict[str, bool]:
    """Detect what capabilities a model has based on its name."""
    model_lower = model_name.lower()

    # Check against known models
    has_vision = any(vm in model_lower for vm in VISION_CAPABLE_MODELS)
    has_function_calling = any(fm in model_lower for fm in FUNCTION_CALLING_MODELS)
    has_streaming = any(sm in model_lower for sm in STREAMING_MODELS)

    # Heuristics for unknown models
    if not has_vision:
        # Check for vision-related keywords
        vision_keywords = ["vision", "vl", "llava", "gemini", "gpt-4o", "claude-3", "claude-sonnet-4", "claude-opus-4"]
        has_vision = any(kw in model_lower for kw in vision_keywords)

    if not has_function_calling:
        # Most modern models support it
        function_keywords = ["gpt", "claude", "gemini"]
        has_function_calling = any(kw in model_lower for kw in function_keywords)

    # Streaming is pretty standard
    if not has_streaming:
        has_streaming = True  # Assume yes for unknown models

    return {
        "vision": has_vision,
        "function_calling": has_function_calling,
        "streaming": has_streaming,
    }


# ═══════════════════════════════════════════════════════════════════
#  Simple input helpers — NO interactive redraw, NO flicker
# ═══════════════════════════════════════════════════════════════════


def _simple_choice(
    title: str,
    options: List[str],
    descriptions: List[str],
    default: int = 0,
) -> int:
    """Print a numbered list and read a number from stdin. No cursor manipulation, no screen redraw, no flicker."""
    n = len(options)
    if HAS_RICH:
        console.print()
        console.print(f"  [bold {_C_ACCENT}]▸[/] [bold]{title}[/]")
        console.print()
        for i, (opt, desc) in enumerate(zip(options, descriptions)):
            marker = f"[{_C_ACCENT}]▸[/]" if i == default else " "
            console.print(f"  {marker} [{_C_BLUE_DIM}]{i + 1:>2}[/] [bold]{opt}[/]")
            if i < len(descriptions) and descriptions[i]:
                console.print(f"           [{_C_BLUE_DIM}]{descriptions[i]}[/]")
        console.print()
    else:
        sys.stdout.write(f"\n  {_A_CYAN}{_A_BOLD}▸ {title}{_A_RESET}\n\n")
        for i, (opt, desc) in enumerate(zip(options, descriptions)):
            marker = f"{_A_CYAN}▸{_A_RESET}" if i == default else " "
            sys.stdout.write(f"  {marker} {_A_DIM_BLUE}{i+1:>2}{_A_RESET} {_A_BOLD}{opt}{_A_RESET}\n")
            if i < len(descriptions) and descriptions[i]:
                sys.stdout.write(f"           {_A_DIM_BLUE}{descriptions[i]}{_A_RESET}\n")
        sys.stdout.write("\n")
        sys.stdout.flush()

    default_label = default + 1
    while True:
        try:
            raw = input(f"  Enter choice (1-{n}, default {default_label}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if not raw:
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < n:
                return idx
        except ValueError:
            pass
        print(f"  Invalid choice. Enter a number 1-{n}.")


def _simple_yes_no(label: str, default: bool = False) -> bool:
    """Simple y/n prompt — no interactive UI, no flicker."""
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            raw = input(f"  {label} [{hint}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please enter y or n.")


def _simple_prompt(label: str, default: str = "", password: bool = False) -> str:
    """Simple text input — no interactive UI, no flicker."""
    hint = f" [{default}]" if default else ""
    if password:
        try:
            import getpass
            raw = getpass.getpass(f"  {label}{hint}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return default
    else:
        try:
            raw = input(f"  {label}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
    return raw if raw else default


# ═══════════════════════════════════════════════════════════════════
#  Visual helpers
# ═══════════════════════════════════════════════════════════════════


def _step_progress(step: int, total: int, title: str) -> None:
    """Blue-accented step header."""
    if HAS_RICH:
        console.print()
        console.rule(
            f"  [bold {_C_ACCENT}]Step {step}/{total}[/]  ·  "
            f"[bold white]{title}[/]",
            style="bright_blue",
        )
        console.print()
    else:
        line = "─" * 54
        sys.stdout.write(f"\n{_A_BLUE}{line}{_A_RESET}\n")
        sys.stdout.write(
            f"  {_A_CYAN}{_A_BOLD}Step {step}/{total}{_A_RESET}"
            f"  ·  {_A_BOLD}{title}{_A_RESET}\n"
        )
        sys.stdout.write(f"{_A_BLUE}{line}{_A_RESET}\n\n")
        sys.stdout.flush()


def _print_section(title: str) -> None:
    """Blue ▸ marker for sub-sections."""
    if HAS_RICH:
        console.print(f"\n  [bold {_C_ACCENT}]▸[/] [bold]{title}[/]")
    else:
        sys.stdout.write(f"\n  {_A_CYAN}{_A_BOLD}▸{_A_RESET} {_A_BOLD}{title}{_A_RESET}\n")
        sys.stdout.flush()


def _print_kv(label: str, value: str, indent: int = 0) -> None:
    """Aligned key→value with blue label, cyan value."""
    pad = " " * indent
    if HAS_RICH:
        console.print(
            f"{pad}  [{_C_BLUE_DIM}]{label:<22}[/] "
            f"[{_C_ACCENT}]{value}[/]"
        )
    else:
        sys.stdout.write(
            f"{pad}  {_A_DIM_BLUE}{label:<22}{_A_RESET} "
            f"{_A_CYAN}{value}{_A_RESET}\n"
        )
        sys.stdout.flush()


def _print_setup_banner() -> None:
    """Blue-premium brand panel — setup variant."""
    version = __version__

    if HAS_RICH:
        brand = Text()
        brand.append(f"  ◆  MINXG", style="bold gold3 on rgb(12,18,40)")
        brand.append(
            f"\n     Multilingual Intelligence eXchange Gateway",
            style="dim white on rgb(12,18,40)",
        )
        brand.append(
            f"\n     Setup Wizard  ·  Interactive Configuration",
            style="bold white on rgb(12,18,40)",
        )
        brand.append(
            f"\n     Version {version} (shitshow cleanup)",
            style="dim silver on rgb(12,18,40)",
        )

        console.print()
        console.print(Panel(
            brand,
            border_style="bright_blue",
            padding=(1, 2),
            width=72,
            title="[bold gold3]◆ setup[/bold gold3]",
            subtitle=f"[dim]v{version}[/dim]",
        ))

        notice = Text()
        notice.append(
            "  This wizard configures your AI provider, model, vision,\n"
            "  and runtime settings. All changes are saved to config.yaml\n"
            "  and can be re-run anytime with: minxg setup\n",
            style="dim white on rgb(16,42,105)",
        )
        console.print(Panel(
            notice,
            border_style="deep_sky_blue3",
            padding=(0, 2),
            width=72,
        ))
        console.print()
    else:
        bar = "═" * 68
        sys.stdout.write("\n")
        sys.stdout.write(f"{Colors.INDIGO}{Colors.BOLD}╔{bar}╗{Colors.RESET}\n")
        line = f"  {_A_GOLD}{_A_BOLD}◆  MINXG{_A_RESET}  {_A_DIM}Multilingual Intelligence eXchange Gateway{_A_RESET}"
        sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{line}{' ' * max(0, 68 - _visual_width(line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        line = f"     Setup Wizard  ·  Interactive Configuration"
        sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{_A_BOLD}{line}{' ' * max(0, 68 - len(line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        line = f"     Version {version} (shitshow cleanup)"
        sys.stdout.write(f"{Colors.INDIGO}║{_A_BG_DEEP}{_A_DIM}{line}{' ' * max(0, 68 - len(line))}{Colors.RESET}{Colors.INDIGO}║{Colors.RESET}\n")
        sys.stdout.write(f"{Colors.INDIGO}╚{bar}╝{Colors.RESET}\n\n")
        for ln in [
            "  This wizard configures your AI provider, model, vision,",
            "  and runtime settings. Re-run anytime with: minxg setup",
        ]:
            sys.stdout.write(f"{Colors.bg('17')}{Colors.SLATE}{ln}{Colors.RESET}\n")
        sys.stdout.write("\n")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════
#  Path helpers
# ═══════════════════════════════════════════════════════════════════


def _project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def _config_path() -> Path:
    return _project_root() / "config.yaml"


def _env_path() -> Path:
    return _project_root() / ".env"


# ═══════════════════════════════════════════════════════════════════
#  Config load / save
# ═══════════════════════════════════════════════════════════════════


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
            print_warning(f"Load failed: {e}")
    return {}


def save_config(config: Dict[str, Any]) -> None:
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    try:
        tmp = config_path.with_suffix(config_path.suffix + ".tmp")
        with open(tmp, "w") as f:
            yaml.dump(config, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)
        os.replace(tmp, config_path)
    except Exception:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)
    print_success(f"Config saved → {config_path}")


def save_env(key: str, value: str) -> None:
    """Save a key=value pair to the .env file."""
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


# ═══════════════════════════════════════════════════════════════════
#  Model fetching
# ═══════════════════════════════════════════════════════════════════


def _fetch_models(base_url: str, api_key: str) -> List[str]:
    """Fetch available models from the provider's /models endpoint."""
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


def _prompt_model_with_fetch(
    provider_info: dict,
    existing_model: str | None,
    base_url: str,
    api_key: str,
) -> str:
    """Model picker — numbered list when models are fetched."""
    default_model = existing_model or provider_info["default_model"]
    fetched = _fetch_models(base_url, api_key)

    if fetched and len(fetched) > 1:
        descs = [f"from {provider_info['name']}" for _ in fetched]
        default_idx = 0
        if default_model in fetched:
            default_idx = fetched.index(default_model)
        idx = _simple_choice("Select model", fetched, descs, default=default_idx)
        return fetched[idx]

    if not fetched:
        print_warning("Could not fetch models from provider — enter manually")
    elif len(fetched) == 1:
        print_info(f"Only one model available: {fetched[0]}")
        return fetched[0]

    return _simple_prompt("Enter model name", default_model)


# ═══════════════════════════════════════════════════════════════════
#  Step 1 — Language (quick)
# ═══════════════════════════════════════════════════════════════════


def setup_language(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 1: Language — hardcoded to English for now."""
    _step_progress(1, TOTAL_STEPS_QUICK if config.get("_quick") else TOTAL_STEPS_FULL, "Language")
    config["lang"] = "en"
    print_success("Language: English")


# ═══════════════════════════════════════════════════════════════════
#  Step 2 — AI Provider + Model + Key + URL
# ═══════════════════════════════════════════════════════════════════


def setup_ai_provider(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 2: AI Provider selection with model and credentials."""
    total = TOTAL_STEPS_QUICK if config.get("_quick") else TOTAL_STEPS_FULL
    _step_progress(2, total, "AI Provider")

    # Provider selection
    provider_names = [f"{p['emoji']} {p['name']}" for p in AI_PROVIDERS.values()]
    provider_descriptions = [p["description"] for p in AI_PROVIDERS.values()]

    existing_provider = existing.get("ai", {}).get("provider")
    default_idx = 0
    if existing_provider and existing_provider in AI_PROVIDERS:
        provider_keys = list(AI_PROVIDERS.keys())
        if existing_provider in provider_keys:
            default_idx = provider_keys.index(existing_provider)

    selected = _simple_choice(
        "Select AI provider",
        provider_names, provider_descriptions, default=default_idx,
    )
    provider_key = list(AI_PROVIDERS.keys())[selected]
    provider_info = AI_PROVIDERS[provider_key]

    config["ai"] = config.get("ai", {})
    config["ai"]["provider"] = provider_key
    print_success(f"Provider → {provider_info['name']}")

    if provider_key == "local":
        print_info("Local mode — set base_url to your server endpoint")
        config["ai"]["model"] = ""
        config["ai"]["base_url"] = ""
        config["ai"]["api_key"] = ""
        return

    # API URL
    _print_section("API URL")
    base_url = _simple_prompt(
        "Enter API URL (or Enter to skip)",
        existing.get("ai", {}).get("base_url") or provider_info["default_url"],
    )
    config["ai"]["base_url"] = base_url
    print_success("API URL configured")

    # API Key
    if provider_info["needs_api_key"]:
        _print_section("API Key")
        existing_key = existing.get("ai", {}).get("api_key", "")
        key_hint = ("***" + existing_key[-4:]) if existing_key else ""
        api_key = _simple_prompt("Enter API key", key_hint, password=True)
        config["ai"]["api_key"] = api_key
        print_success("API key configured")

    # Model selection
    _print_section("Model Selection")
    model = _prompt_model_with_fetch(
        provider_info,
        existing.get("ai", {}).get("model"),
        base_url,
        config["ai"].get("api_key", ""),
    )
    config["ai"]["model"] = model
    print_success(f"Model → {model}")

    # Detect model capabilities
    _print_section("Model Capabilities")
    capabilities = detect_model_capabilities(model)

    print_info(f"Detected capabilities for {model}:")
    if capabilities["vision"]:
        print_info("  ✓ Vision (image understanding)")
    if capabilities["function_calling"]:
        print_info("  ✓ Function calling")
    if capabilities["streaming"]:
        print_info("  ✓ Streaming")

    # Store detected capabilities
    config["ai"]["capabilities"] = capabilities


# ═══════════════════════════════════════════════════════════════════
#  Step 3 — Vision Configuration (NEW)
# ═══════════════════════════════════════════════════════════════════


def setup_vision(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 3: Vision configuration — does your model see images?"""
    total = TOTAL_STEPS_QUICK if config.get("_quick") else TOTAL_STEPS_FULL
    _step_progress(3, total, "Vision Configuration")

    ai = config.get("ai", {})
    capabilities = ai.get("capabilities", {})
    model = ai.get("model", "")

    # Check if model is vision-capable
    is_vision_capable = capabilities.get("vision", False)

    if not is_vision_capable:
        print_info(f"Model '{model}' does not appear to support vision.")
        print_info("Skipping vision configuration.")
        config["vision"] = {"enabled": False}
        return

    _print_section("Vision Settings")

    # Ask if user wants to enable vision
    existing_vision = existing.get("vision", {})
    vision_enabled = _simple_yes_no(
        f"Enable vision for {model}?",
        default=existing_vision.get("enabled", True),
    )

    if not vision_enabled:
        config["vision"] = {"enabled": False}
        print_info("Vision disabled")
        return

    # Vision settings
    config["vision"] = {"enabled": True}

    # Max image size (MB)
    max_size = _simple_prompt(
        "Max image size (MB)",
        str(existing_vision.get("max_size_mb", 20)),
    )
    try:
        config["vision"]["max_size_mb"] = int(max_size)
    except ValueError:
        config["vision"]["max_size_mb"] = 20

    # Supported formats
    _print_section("Supported Image Formats")
    formats = ["jpeg", "png", "webp", "gif"]
    format_choices = [f"Enable {fmt.upper()}" for fmt in formats]
    format_descs = [
        "JPEG images (most common)",
        "PNG images (lossless)",
        "WebP images (modern format)",
        "GIF images (animated)",
    ]

    # Default: all enabled
    enabled_formats = []
    for i, fmt in enumerate(formats):
        default_on = existing_vision.get("formats", ["jpeg", "png", "webp", "gif"])
        is_enabled = fmt in default_on
        if _simple_yes_no(format_choices[i], default=is_enabled):
            enabled_formats.append(fmt)

    config["vision"]["formats"] = enabled_formats if enabled_formats else ["jpeg", "png", "webp"]

    # Vision model (separate from chat model)
    _print_section("Vision Model")
    vision_model = _simple_prompt(
        "Vision model (leave empty to use same as chat)",
        existing_vision.get("model", ""),
    )
    if vision_model:
        config["vision"]["model"] = vision_model

    print_success(f"Vision enabled (formats: {', '.join(config['vision']['formats'])})")


# ═══════════════════════════════════════════════════════════════════
#  Step 4 — AI Core Limits
# ═══════════════════════════════════════════════════════════════════


def setup_ai_limits(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 4: AI core limits — max_tokens, context window, concurrency."""
    total = TOTAL_STEPS_FULL
    _step_progress(4, total, "AI Core Limits")

    ai = config.setdefault("ai", {})

    _print_section("Max Output Tokens")
    default_mt = str(existing.get("ai", {}).get("max_tokens", 4096))
    mt = _simple_prompt("Maximum output tokens per response", default_mt)
    try:
        ai["max_tokens"] = int(mt)
    except ValueError:
        ai["max_tokens"] = 4096
    print_success(f"max_tokens = {ai['max_tokens']}")

    _print_section("Context Window")
    default_cw = str(existing.get("ai", {}).get("context_window", 32768))
    cw = _simple_prompt("Context window size (tokens of history to retain)", default_cw)
    try:
        ai["context_window"] = int(cw)
    except ValueError:
        ai["context_window"] = 32768
    print_success(f"context_window = {ai['context_window']}")

    _print_section("Concurrency")
    default_cc = str(existing.get("ai", {}).get("concurrency", 4))
    cc = _simple_prompt("Parallel tool-call concurrency (1-32)", default_cc)
    try:
        ai["concurrency"] = max(1, min(32, int(cc)))
    except ValueError:
        ai["concurrency"] = 4
    print_success(f"concurrency = {ai['concurrency']}")

    # Reasoning effort
    _print_section("Reasoning Effort")
    provider_key = ai.get("provider", "")
    supported_levels = REASONING_BY_PROVIDER.get(provider_key)
    level_names = [name for name, _ in REASONING_LEVELS]
    level_descs = [desc for _, desc in REASONING_LEVELS]
    if supported_levels:
        ordered = [n for n in level_names if n in supported_levels] + [
            n for n in level_names if n not in supported_levels
        ]
    else:
        ordered = level_names
    existing_level = existing.get("ai", {}).get("reasoning_effort") or "medium"
    default_idx = 0
    for i, n in enumerate(ordered):
        if resolve_reasoning_level(provider_key, existing_level) == n:
            default_idx = i
            break
    selected_idx = _simple_choice(
        "Select reasoning effort",
        ordered, level_descs, default=default_idx,
    )
    ai["reasoning_effort"] = ordered[selected_idx]
    print_success(f"reasoning_effort = {ai['reasoning_effort']}")

    # Temperature
    _print_section("Temperature")
    existing_temp = existing.get("ai", {}).get("temperature", 0.3)
    temp = _simple_prompt("Temperature (0.0-2.0)", str(existing_temp))
    try:
        ai["temperature"] = min(2.0, max(0.0, float(temp)))
    except ValueError:
        ai["temperature"] = 0.3
    print_success(f"temperature = {ai['temperature']}")


# ═══════════════════════════════════════════════════════════════════
#  Step 5 — Usage Mode
# ═══════════════════════════════════════════════════════════════════


def setup_mode(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 5: Usage mode selection."""
    total = TOTAL_STEPS_FULL
    _step_progress(5, total, "Usage Mode")

    mode_options = [
        (chr(0x1F4AC), "Chat CLI (default)"),
        (chr(0x1F310), "API Gateway"),
        (chr(0x2699) + chr(0xFE0F), "Both (chat + gateway)"),
    ]
    mode_choices = [f"{e} {n}" for e, n in mode_options]
    mode_descs = [
        "Talk to the model directly from your terminal",
        "Expose an OpenAI-compatible v1 endpoint for other tools",
        "Local chat + an OpenAI-compatible HTTP endpoint on $PORT",
    ]

    existing_mode = existing.get("mode", "chat")
    mode_map = {"chat": 0, "gateway": 1, "both": 2}
    default_idx = mode_map.get(existing_mode, 0)

    mode_idx = _simple_choice("Pick a usage mode", mode_choices, mode_descs, default=default_idx)
    config["mode"] = ("chat", "gateway", "both")[mode_idx]
    print_success(f"Mode → {config['mode']}")


# ═══════════════════════════════════════════════════════════════════
#  Step 6 — Gateway
# ═══════════════════════════════════════════════════════════════════


def setup_gateway(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 6: Gateway configuration."""
    total = TOTAL_STEPS_FULL
    _step_progress(6, total, "Gateway")

    existing_gw = existing.get("gateway", {})

    host = _simple_prompt("Gateway host", existing_gw.get("host", "0.0.0.0"))
    port = _simple_prompt("Gateway port", str(existing_gw.get("port", 19001)))

    config["gateway"] = {
        "host": host,
        "port": int(port) if port.isdigit() else 19001,
    }

    auto = _simple_yes_no(
        "Auto-start gateway on launch?",
        default=existing_gw.get("auto_start", False),
    )
    config["gateway"]["auto_start"] = auto

    print_success("Gateway configured")


# ═══════════════════════════════════════════════════════════════════
#  Step 7 — Environment
# ═══════════════════════════════════════════════════════════════════


def setup_environment(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 7: Environment configuration."""
    total = TOTAL_STEPS_FULL
    _step_progress(7, total, "Environment")

    existing_env = existing.get("environment", {})

    # Log level
    _print_section("Log Level")
    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    log_descs = [
        "Debug (all messages)",
        "Info (normal operation)",
        "Warning",
        "Error only",
    ]
    existing_log = existing_env.get("log_level", "INFO")
    log_idx = log_levels.index(existing_log) if existing_log in log_levels else 1
    selected_log = _simple_choice("Log level", log_levels, log_descs, default=log_idx)

    debug = _simple_yes_no("Enable debug mode?", default=existing_env.get("debug", False))

    # Workers
    _print_section("Workers")
    workers_port = _simple_prompt("Workers RPC port", str(existing_env.get("workers_port", 19001)))
    workers_autostart = _simple_yes_no(
        "Auto-start workers on launch?",
        default=existing_env.get("workers_autostart", True),
    )
    health_interval = _simple_prompt(
        "Health check interval (seconds)",
        str(existing_env.get("health_check_interval", 60)),
    )

    # Performance
    _print_section("Performance Optimization")
    print_info("Mobile optimization reduces memory/CPU usage")
    existing_perf = existing.get("perf", {})
    mobile_opt = _simple_yes_no(
        "Performance Optimization",
        default=existing_perf.get("mobile_optimization", True),
    )
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


# ═══════════════════════════════════════════════════════════════════
#  Step 8 — Browser Search
# ═══════════════════════════════════════════════════════════════════


def setup_browser_search(config: Dict[str, Any], existing: Dict[str, Any]) -> None:
    """Step 8: Browser search configuration."""
    total = TOTAL_STEPS_FULL
    _step_progress(8, total, "Browser Search")

    existing_bs = existing.get("browser_search", {})

    enabled = _simple_yes_no(
        "Enable browser search for AI",
        default=existing_bs.get("enabled", False),
    )
    if not enabled:
        config["browser_search"] = {"enabled": False}
        print_info("Browser search disabled")
        return

    _print_section("Search Method")
    api_types = ["User's own browser", "Custom AI search API"]
    api_type_idx = 0 if existing_bs.get("api_type") == "user" else 1
    selected_api = _simple_choice(
        "Search method",
        api_types,
        ["Use system browser", "Use AI search API endpoint"],
        default=api_type_idx,
    )
    api_type = "user" if selected_api == 0 else "api"

    config["browser_search"] = {"enabled": True, "api_type": api_type}

    if api_type == "api":
        _print_section("API Configuration")
        api_url = _simple_prompt("API URL", existing_bs.get("api_url", ""))
        config["browser_search"]["api_url"] = api_url

        api_key = _simple_prompt("API Key", existing_bs.get("api_key", ""), password=True)
        if api_key:
            config["browser_search"]["api_key"] = api_key

        model = _simple_prompt("Model (optional)", existing_bs.get("model", ""))
        if model:
            config["browser_search"]["model"] = model

    print_success("Browser search configured")


# ═══════════════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════════════


def show_summary(config: Dict[str, Any]) -> None:
    """Blue-themed summary panel."""
    if HAS_RICH:
        t = Table(show_header=False, box=None, padding=(0, 1), width=64)
        t.add_column(style=f"dim {_C_BLUE_DIM}", justify="right", width=22)
        t.add_column(style=f"bold {_C_ACCENT}")

        ai = config.get("ai", {})
        t.add_row("Language", config.get("lang", "en"))
        t.add_row("Provider", ai.get("provider", "—"))
        t.add_row("Model", ai.get("model", "—"))
        t.add_row("API URL", ai.get("base_url", "—") or "—")

        # Vision
        vision = config.get("vision", {})
        t.add_row("Vision", "enabled" if vision.get("enabled") else "disabled")
        if vision.get("enabled"):
            t.add_row("  Formats", ", ".join(vision.get("formats", [])))

        if ai.get("max_tokens"):
            t.add_row("Max Tokens", str(ai["max_tokens"]))
        if ai.get("temperature") is not None:
            t.add_row("Temperature", str(ai["temperature"]))
        if ai.get("reasoning_effort"):
            t.add_row("Reasoning", str(ai["reasoning_effort"]))
        if ai.get("context_window"):
            t.add_row("Context Window", str(ai["context_window"]))
        if ai.get("concurrency"):
            t.add_row("Concurrency", str(ai["concurrency"]))

        gw = config.get("gateway", {})
        if gw:
            t.add_row("Gateway", f"{gw.get('host', '0.0.0.0')}:{gw.get('port', 19001)}")

        env = config.get("environment", {})
        if env:
            t.add_row("Log Level", env.get("log_level", "INFO"))
            t.add_row("Debug", str(env.get("debug", False)))

        perf = config.get("perf", {})
        if perf:
            t.add_row("Performance",
                      "enabled" if perf.get("mobile_optimization", True) else "disabled")

        bs = config.get("browser_search", {})
        if bs.get("enabled"):
            t.add_row("Browser Search", f"enabled ({bs.get('api_type', 'user')})")
        else:
            t.add_row("Browser Search", "disabled")

        if config.get("mode"):
            t.add_row("Usage Mode", str(config["mode"]))

        console.print()
        console.print(Panel(
            t,
            title=f"[bold {_C_ACCENT}]◆ Configuration Review[/]",
            border_style="bright_blue",
            padding=(1, 2),
            width=72,
        ))
        console.print()
    else:
        line = "─" * 54
        sys.stdout.write(f"\n{_A_BLUE}{line}{_A_RESET}\n")
        sys.stdout.write(f"  {_A_CYAN}{_A_BOLD}◆ Configuration Review{_A_RESET}\n")
        sys.stdout.write(f"{_A_BLUE}{line}{_A_RESET}\n\n")

        ai = config.get("ai", {})
        _print_kv("Language", config.get("lang", "en"))
        _print_kv("Provider", ai.get("provider", "—"))
        _print_kv("Model", ai.get("model", "—"))
        _print_kv("API URL", ai.get("base_url", "—") or "—")

        vision = config.get("vision", {})
        _print_kv("Vision", "enabled" if vision.get("enabled") else "disabled")

        if ai.get("max_tokens"):
            _print_kv("Max Tokens", str(ai["max_tokens"]))
        if ai.get("temperature") is not None:
            _print_kv("Temperature", str(ai["temperature"]))
        if ai.get("reasoning_effort"):
            _print_kv("Reasoning", str(ai["reasoning_effort"]))

        gw = config.get("gateway", {})
        if gw:
            _print_kv("Gateway", f"{gw.get('host', '0.0.0.0')}:{gw.get('port', 19001)}")

        env = config.get("environment", {})
        if env:
            _print_kv("Log Level", env.get("log_level", "INFO"))
            _print_kv("Debug", str(env.get("debug", False)))

        perf = config.get("perf", {})
        if perf:
            _print_kv("Performance",
                      "enabled" if perf.get("mobile_optimization", True) else "disabled")

        bs = config.get("browser_search", {})
        if bs.get("enabled"):
            _print_kv("Browser Search", f"enabled ({bs.get('api_type', 'user')})")
        else:
            _print_kv("Browser Search", "disabled")

        sys.stdout.write(f"\n{_A_BLUE}{line}{_A_RESET}\n\n")
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════
#  Post-setup hints
# ═══════════════════════════════════════════════════════════════════


def _post_setup_hints(config: Dict[str, Any]) -> None:
    """Blue celebration panel + quick-reference hint table."""
    print()

    if HAS_RICH:
        console.print(Panel.fit(
            f"[bold {_C_ACCENT}]✓ Setup Complete[/]\n"
            f"[dim]Your configuration is saved. Re-run with:[/]\n"
            f"[bold]minxg setup[/]",
            title=f"[bold {_C_ACCENT}]MINXG[/]",
            border_style="bright_blue",
            padding=(1, 4),
        ))
        print()

        t = Table.grid(padding=(0, 3))
        t.add_column(style=f"bold {_C_ACCENT}", justify="right")
        t.add_column(style="dim")
        t.add_row("minxg",               "start the TUI chat")
        t.add_row("minxg chat",          "alias for the chat CLI")
        t.add_row("minxg gateway",        "OpenAI-compatible v1 endpoint (--detach for background)")
        t.add_row("minxg doctor",        "self-check (config + tools + extensions)")
        t.add_row("minxg --help",        "command cheatsheet")
        t.add_row("minxg -v status",     "runtime status with verbose logging")
        console.print(t)
    else:
        bar = "═" * 54
        sys.stdout.write(f"{_A_BLUE}╔{bar}╗{_A_RESET}\n")
        sys.stdout.write(
            f"{_A_BLUE}║{_A_RESET}{_A_BG_DEEP}  {_A_CYAN}{_A_BOLD}✓ Setup Complete{_A_RESET}"
            f"{' ' * (54 - 18)}{_A_RESET}{_A_BLUE}║{_A_RESET}\n"
        )
        sys.stdout.write(
            f"{_A_BLUE}║{_A_RESET}{_A_BG_DEEP}{_A_DIM}  Config saved. Re-run with: minxg setup"
            f"{' ' * max(0, 54 - 42)}{_A_RESET}{_A_BLUE}║{_A_RESET}\n"
        )
        sys.stdout.write(f"{_A_BLUE}╠{bar}╣{_A_RESET}\n")
        hints = [
            ("minxg",               "start the TUI chat"),
            ("minxg chat",          "alias for the chat CLI"),
            ("minxg gateway",        "OpenAI-compatible v1 endpoint (--detach for background)"),
            ("minxg doctor",        "self-check (config + tools + extensions)"),
            ("minxg --help",        "command cheatsheet"),
            ("minxg -v status",     "runtime status with verbose logging"),
        ]
        for cmd, desc in hints:
            row = f"  {_A_CYAN}{cmd:<22}{_A_RESET} {_A_DIM_BLUE}{desc}{_A_RESET}"
            sys.stdout.write(f"{_A_BLUE}║{_A_RESET}{row}{' ' * max(0, 54 - 24 - len(desc))}{_A_BLUE}║{_A_RESET}\n")
        sys.stdout.write(f"{_A_BLUE}╚{bar}╝{_A_RESET}\n")

    print()


# ═══════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════


def run_setup():
    """Main wizard entry.

    v0.18.3 — two tiers: **Quick** (3 steps) and **Full** (8 steps).
    All menus use simple numbered lists + text input — no flicker.

    Quick: Language → Provider+Model → Vision → Save
    Full:  Language → Provider+Model → Vision → Limits → Mode → Gateway → Env → Search → Save
    """
    clear_screen()
    _print_setup_banner()

    existing = load_existing_config()
    if existing:
        print_info("Found existing config — will prompt for changes.")

    # Tier selection
    tier_choices = [
        "Quick  (3 steps — provider, vision, save)",
        "Full   (8 steps — everything, the whole damn thing)",
    ]
    tier_descs = [
        "Fast path — gets the AI core working in under a minute.",
        "Everything — mode, gateway port, env, browser search, the works.",
    ]
    tier_idx = _simple_choice("Choose wizard tier", tier_choices, tier_descs, default=0)
    quick = (tier_idx == 0)

    config: Dict[str, Any] = {"_quick": quick}

    print_success(f"Tier: {'Quick (3 steps)' if quick else 'Full (8 steps)'}")

    # Step 1 — Language
    setup_language(config, existing)

    # Step 2 — AI Provider + Model
    setup_ai_provider(config, existing)

    if quick:
        # Quick mode: just vision then save
        setup_vision(config, existing)
    else:
        # Full mode: everything
        setup_ai_limits(config, existing)
        setup_mode(config, existing)
        setup_gateway(config, existing)
        setup_environment(config, existing)
        setup_browser_search(config, existing)

    # Remove internal flag
    config.pop("_quick", None)

    # Review + save
    show_summary(config)

    if _simple_yes_no("Save configuration?", default=True):
        save_config(config)
        if config.get("ai", {}).get("api_key"):
            save_env("AI_API_KEY", config["ai"]["api_key"])
        _post_setup_hints(config)
    else:
        print_info("Setup cancelled — no changes saved.")

    print()
    print_success("Goodbye!")


if __name__ == "__main__":
    run_setup()
