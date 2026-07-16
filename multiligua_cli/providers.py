"""
multiligua_cli/providers.py — MINXG AI provider registry (v0.18.3).
Single source of truth for all model providers, base URLs, env var names,
and per-provider context-length caps.

Each provider is a flat dataclass-like dict so the gateway and CLI config
wizard both consume it without importing each other.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import os as _os_mod

# ── Back-compat re-exports for setup.py / tui_chat.py / legacy code ---
# The old providers.py module shipped these constants in addition to the
# provider/model tables.  Old code imports them by name, so we keep them.
REASONING_LEVELS = [
    "none", "minimal", "low", "medium", "high", "xhigh",
]

# Coarse default mapping — used by /reasoning command in classical providers.
REASONING_BY_PROVIDER = {
    "openai":       "medium",
    "anthropic":    "low",
    "google":       "low",
    "deepseek":     "high",
    "xai":          "medium",
    "alibaba":      "medium",
    "moonshot":     "low",
    "zhipu":        "low",
    "minimax":      "medium",
    "nvidia":       "low",
    "ollama":       "low",
    "llamacpp":     "low",
    "vllm":         "low",
    "mistral":      "low",
    "huggingface":  "low",
}


def resolve_reasoning_level(provider: str, requested: Optional[str] = None) -> str:
    """Return a reasoning_level string for the given provider.

    Honours explicit request when valid, else falls back to the provider-default
    from ``REASONING_BY_PROVIDER``, else to "minimal".
    """
    if requested:
        r = requested.strip().lower()
        # accept "x-high" as alias for xhigh
        r = {"x-high": "xhigh"}.get(r, r)
        if r in REASONING_LEVELS:
            return r
    default = REASONING_BY_PROVIDER.get(provider)
    return default if default in REASONING_LEVELS else "minimal"


# Alias names that downstream code still imports.  These are populated below
# from the real registry so legacy callers see the same shape they always did.
AI_PROVIDERS = _AI_PROVIDERS_LIST = None  # populated at module load

# ── Provider registry ─────────────────────────────────────────────────
# fmt: off
PROVIDER_REGISTRY: List[Dict] = [
    # ── Major cloud ─────────────────────────────────────────────────
    {
        "slug": "openrouter",
        "display": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "context_cap": 1_000_000,
        "tier": "enterprise",
        "docs": "https://openrouter.ai/docs",
    },
    {
        "slug": "nvidia",
        "display": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://build.nvidia.com/explore/discover",
    },
    {
        "slug": "deepseek",
        "display": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://platform.deepseek.com/api-docs",
    },
    {
        "slug": "anthropic",
        "display": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "context_cap": 200_000,
        "tier": "enterprise",
        "docs": "https://docs.anthropic.com/en/api",
    },
    {
        "slug": "openai",
        "display": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://platform.openai.com/docs",
    },
    {
        "slug": "google",
        "display": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GOOGLE_API_KEY",
        "context_cap": 2_000_000,
        "tier": "enterprise",
        "docs": "https://ai.google.dev/gemini-api/docs/openai",
    },
    {
        "slug": "xai",
        "display": "xAI Grok",
        "base_url": "https://api.x.ai/v1",
        "env_key": "XAI_API_KEY",
        "context_cap": 1_000_000,
        "tier": "enterprise",
        "docs": "https://docs.x.ai/docs",
    },
    {
        "slug": "minimax",
        "display": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
        "env_key": "MINIMAX_API_KEY",
        "context_cap": 1_000_000,
        "tier": "enterprise",
        "docs": "https://platform.minimax.chat",
    },
    {
        "slug": "alibaba",
        "display": "Alibaba DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://help.aliyun.com/document_detail/2712195.html",
    },
    {
        "slug": "moonshot",
        "display": "Moonshot / Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "env_key": "MOONSHOT_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://platform.moonshot.cn/docs",
    },
    {
        "slug": "zhipu",
        "display": "Zhipu GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "GLM_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://open.bigmodel.cn/dev/api",
    },
    {
        "slug": "mistral",
        "display": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://docs.mistral.ai/api",
    },
    {
        "slug": "huggingface",
        "display": "Hugging Face",
        "base_url": "https://api-inference.huggingface.co/v1",
        "env_key": "HF_TOKEN",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://huggingface.co/docs/api-inference",
    },
    {
        "slug": "cohere",
        "display": "Cohere",
        "base_url": "https://api.cohere.com/v1",
        "env_key": "COHERE_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://docs.cohere.com/reference/about",
    },
    {
        "slug": "together",
        "display": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://docs.together.ai/reference",
    },
    {
        "slug": "fireworks",
        "display": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "env_key": "FIREWORKS_API_KEY",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://docs.fireworks.ai/api-reference",
    },
    {
        "slug": "groq",
        "display": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://console.groq.com/docs/api-reference",
    },
    {
        "slug": "cerebras",
        "display": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "env_key": "CEREBRAS_API_KEY",
        "context_cap": 128_000,
        "tier": "enterprise",
        "docs": "https://inference-docs.cerebras.ai/introduction",
    },
    {
        "slug": "perplexity",
        "display": "Perplexity",
        "base_url": "https://api.perplexity.ai",
        "env_key": "PERPLEXITY_API_KEY",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://docs.perplexity.ai",
    },
    {
        "slug": "qwen_oauth",
        "display": "Qwen (OAuth)",
        "base_url": None,  # set via OAuth flow
        "env_key": "QWEN_OAUTH_TOKEN",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://tongyi.aliyun.com",
    },
    {
        "slug": "github_copilot",
        "display": "GitHub Copilot",
        "base_url": "https://api.githubcopilot.com/v1",
        "env_key": "COPILOT_GITHUB_TOKEN",
        "context_cap": 128_000,
        "tier": "community",
        "docs": "https://docs.github.com/en/copilot",
    },
    # ── Local / self-hosted ──────────────────────────────────────────
    {
        "slug": "ollama",
        "display": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "env_key": None,
        "context_cap": 128_000,
        "tier": "local",
        "docs": "https://ollama.com",
    },
    {
        "slug": "llamacpp",
        "display": "llama.cpp (local)",
        "base_url": "http://localhost:8080/v1",
        "env_key": None,
        "context_cap": 128_000,
        "tier": "local",
        "docs": "https://github.com/ggerganov/llama.cpp",
    },
    {
        "slug": "vllm",
        "display": "vLLM (local/self-host)",
        "base_url": "http://localhost:8000/v1",
        "env_key": None,
        "context_cap": 200_000,
        "tier": "local",
        "docs": "https://docs.vllm.ai/en/stable",
    },
    {
        "slug": "custom",
        "display": "Custom / BYO endpoint",
        "base_url": None,  # user-provided
        "env_key": "CUSTOM_API_KEY",
        "context_cap": 128_000,
        "tier": "local",
        "docs": None,
    },
]

# ── Model catalogue ──────────────────────────────────────────────────
# Maps provider_slug → list of {model_id, display_name, context_window, vision?, reasoning?}
MODEL_CATALOGUE: Dict[str, List[Dict]] = {
    "openrouter": [
        {"id": "openai/gpt-5-pro",        "display": "GPT-5 Pro",          "ctx": 128_000, "vision": True,  "reasoning": True},
        {"id": "anthropic/claude-sonnet-4","display": "Claude Sonnet 4",     "ctx": 200_000, "vision": True,  "reasoning": False},
        {"id": "anthropic/claude-opus-4",  "display": "Claude Opus 4",       "ctx": 200_000, "vision": True,  "reasoning": False},
        {"id": "deepseek/deepseek-v4-pro", "display": "DeepSeek V4 Pro",    "ctx": 128_000, "vision": False, "reasoning": True},
        {"id": "deepseek/deepseek-r1",     "display": "DeepSeek R1",        "ctx": 128_000, "vision": False, "reasoning": True},
        {"id": "google/gemini-2.5-pro",    "display": "Gemini 2.5 Pro",     "ctx": 1_000_000, "vision": True, "reasoning": True},
        {"id": "google/gemini-2.5-flash",  "display": "Gemini 2.5 Flash",   "ctx": 1_000_000, "vision": True, "reasoning": True},
        {"id": "x-ai/grok-4",              "display": "Grok 4",             "ctx": 1_000_000, "vision": True,  "reasoning": True},
        {"id": "mistral/mistral-large",    "display": "Mistral Large",      "ctx": 128_000, "vision": True,  "reasoning": False},
        {"id": "meta-llama/llama-4-maverick","display": "Llama 4 Maverick", "ctx": 128_000, "vision": True,  "reasoning": False},
        {"id": "qwen/qwen3-max",           "display": "Qwen3 Max",          "ctx": 128_000, "vision": True,  "reasoning": True},
        {"id": "minimax/minimax-m2.7",     "display": "MiniMax M2.7",       "ctx": 1_000_000, "vision": True, "reasoning": True},
    ],
    "deepseek": [
        {"id": "deepseek-chat",             "display": "DeepSeek V4",    "ctx": 128_000, "vision": False, "reasoning": False},
        {"id": "deepseek-reasoner",          "display": "DeepSeek R1",    "ctx": 128_000, "vision": False, "reasoning": True},
    ],
    "nvidia": [
        {"id": "deepseek-ai/deepseek-v4-pro","display": "DeepSeek V4 Pro (NV)", "ctx": 128_000, "vision": False, "reasoning": True},
        {"id": "google/gemma-3-27b-it",      "display": "Gemma 3 27B",   "ctx": 128_000, "vision": False, "reasoning": False},
        {"id": "nvidia/llama-nemotron",      "display": "Nemotron",       "ctx": 128_000, "vision": False, "reasoning": True},
    ],
    "anthropic": [
        {"id": "claude-sonnet-4-20250514",  "display": "Claude Sonnet 4",  "ctx": 200_000, "vision": True,  "reasoning": False},
        {"id": "claude-opus-4-20250514",    "display": "Claude Opus 4",    "ctx": 200_000, "vision": True,  "reasoning": False},
        {"id": "claude-haiku-4-20250514",   "display": "Claude Haiku 4",   "ctx": 200_000, "vision": True,  "reasoning": False},
    ],
    "openai": [
        {"id": "gpt-5",                      "display": "GPT-5",           "ctx": 128_000, "vision": True,  "reasoning": True},
        {"id": "gpt-5-mini",                 "display": "GPT-5 Mini",      "ctx": 128_000, "vision": True,  "reasoning": True},
    ],
    "google": [
        {"id": "gemini-2.5-pro",            "display": "Gemini 2.5 Pro",   "ctx": 2_000_000, "vision": True, "reasoning": True},
        {"id": "gemini-2.5-flash",          "display": "Gemini 2.5 Flash", "ctx": 1_000_000, "vision": True, "reasoning": True},
    ],
    "xai": [
        {"id": "grok-4",                     "display": "Grok 4",           "ctx": 1_000_000, "vision": True, "reasoning": True},
        {"id": "grok-composer-2.5-fast",     "display": "Grok Composer Fast","ctx":128_000, "vision":False,"reasoning": False},
    ],
    "minimax": [
        {"id": "minimax-m2.7",              "display": "MiniMax M2.7",     "ctx": 1_000_000, "vision": True, "reasoning": True},
    ],
    "alibaba": [
        {"id": "qwen3-max",                  "display": "Qwen3 Max",        "ctx": 128_000, "vision": True, "reasoning": True},
        {"id": "qwen3-plus",                 "display": "Qwen3 Plus",       "ctx": 128_000, "vision": True, "reasoning": False},
    ],
    "moonshot": [
        {"id": "kimi-latest",               "display": "Kimi Latest",      "ctx": 128_000, "vision": True, "reasoning": False},
    ],
    "zhipu": [
        {"id": "glm-4-plus",                "display": "GLM-4 Plus",       "ctx": 128_000, "vision": True, "reasoning": False},
    ],
    "mistral": [
        {"id": "mistral-large-latest",       "display": "Mistral Large",   "ctx": 128_000, "vision": True, "reasoning": False},
        {"id": "codestral-latest",           "display": "Codestral",       "ctx": 256_000, "vision": False, "reasoning": False},
    ],
    "ollama": [
        {"id": "llama3.3:70b",              "display": "Llama 3.3 70B",  "ctx": 128_000, "vision": True, "reasoning": False},
        {"id": "qwen3:14b",                 "display": "Qwen3 14B",     "ctx": 128_000, "vision": True, "reasoning": False},
        {"id": "deepseek-r1:70b",           "display": "DeepSeek R1 70B", "ctx": 128_000, "vision": False, "reasoning": True},
        {"id": "codestral:22b",             "display": "Codestral 22B",  "ctx": 256_000, "vision": False, "reasoning": False},
    ],
    "llamacpp": [
        {"id": "*",                          "display": "Model auto-detected from server", "ctx": 128_000, "vision": False, "reasoning": False},
    ],
    "vllm": [
        {"id": "*",                          "display": "Model chosen at server", "ctx": 200_000, "vision": False, "reasoning": False},
    ],
    "custom": [
        {"id": "*",                          "display": "Custom model (you supply ID)", "ctx": 128_000, "vision": False, "reasoning": False},
    ],
}

MODEL_FALLBACKS = {
    "openrouter": ["deepseek/deepseek-r1", "google/gemini-2.5-flash", "mistral/mistral-large"],
    "deepseek":  ["deepseek-chat"],
    "nvidia":    ["google/gemma-3-27b-it"],
    "anthropic": ["claude-haiku-4-20250514", "claude-sonnet-4-20250514"],
    "openai":    ["gpt-5-mini"],
    "google":    ["gemini-2.5-flash"],
    "xai":       ["grok-composer-2.5-fast"],
    "minimax":   ["minimax-m2.7"],
}

def get_provider(slug: str) -> Optional[Dict]:
    for p in PROVIDER_REGISTRY:
        if p["slug"] == slug:
            return p
    return None

def get_providers_by_tier(tier: str) -> List[Dict]:
    return [p for p in PROVIDER_REGISTRY if p.get("tier") == tier]

def get_models_for_provider(provider_slug: str) -> List[Dict]:
    return MODEL_CATALOGUE.get(provider_slug, [])

def get_fallback_models(provider_slug: str) -> List[str]:
    return MODEL_FALLBACKS.get(provider_slug, [])

def resolve_base_url(provider_slug: str) -> Optional[str]:
    p = get_provider(provider_slug)
    if not p:
        return None
    base = p.get("base_url")
    if base:
        return base
    # custom / ollama / llamacpp — check env override
    import os
    override = os.environ.get(f"MINXG_BASE_URL_{provider_slug.upper()}")
    return override or None


# ── Back-compat lipo — wire AI_PROVIDERS to the real registry now that
#    the registry is fully populated.  Old code expected a {slug: dict}
#    shape; we keep that.
def __build_legacy_ai_providers() -> Dict[str, Dict]:
    out = {}
    for p in PROVIDER_REGISTRY:
        slug = p["slug"]
        models = [m["id"] for m in MODEL_CATALOGUE.get(slug, [])]
        out[slug] = {
            "slug": slug,
            "display": p.get("display") or slug,
            "base_url": p.get("base_url") or "",
            "env_key": p.get("env_key"),
            "api_key": _os_mod.environ.get(p["env_key"]) if p.get("env_key") else None,
            "models": models,
            "tier": p.get("tier", "community"),
            "context_cap": p.get("context_cap", 128_000),
        }
    # Glue env overrides for any *PROVIDER*_BASE_URL too.
    for k, v in _os_mod.environ.items():
        if k.startswith("MINXG_BASE_URL_"):
            slug = k[len("MINXG_BASE_URL_"):].lower()
            if slug in out:
                out[slug]["base_url"] = v
    return out


AI_PROVIDERS = __build_legacy_ai_providers()