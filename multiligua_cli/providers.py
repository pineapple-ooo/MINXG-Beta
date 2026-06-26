"""
multiligua_cli/providers.py — Central registry of supported AI providers.

Each entry MUST have these keys:
  - name          (display name, human-readable, English)
  - emoji         (single emoji glyph for the wizard menu)
  - description   (one-line description)
  - default_model (used when the user hasn't picked one yet)
  - default_url   (API base URL; the OpenAI-compatible endpoint)
  - needs_api_key (bool; False for local servers that don't auth)
"""

AI_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek", "emoji": "🔢",
        "description": "DeepSeek V3 / R1, Chinese open-weights",
        "default_model": "deepseek-chat",
        "default_url": "https://api.deepseek.com/v1",
        "needs_api_key": True,
    },
    "qwen": {
        "name": "Qwen", "emoji": "🐉",
        "description": "Alibaba Qwen Max / Plus via DashScope",
        "default_model": "qwen-max",
        "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "needs_api_key": True,
    },
    "zhipu": {
        "name": "Zhipu GLM", "emoji": "🧊",
        "description": "Zhipu GLM-4 Plus, Chinese frontier model",
        "default_model": "glm-4-plus",
        "default_url": "https://open.bigmodel.cn/api/paas/v4",
        "needs_api_key": True,
    },
    "moonshot": {
        "name": "Moonshot Kimi", "emoji": "🌙",
        "description": "Moonshot Kimi 128k context, Chinese frontier",
        "default_model": "moonshot-v1-128k",
        "default_url": "https://api.moonshot.cn/v1",
        "needs_api_key": True,
    },
    "baichuan": {
        "name": "Baichuan", "emoji": "🏔️",
        "description": "Baichuan 4, Chinese open-weights",
        "default_model": "Baichuan4",
        "default_url": "https://api.baichuan-ai.com/v1",
        "needs_api_key": True,
    },
    "minimax": {
        "name": "MiniMax", "emoji": "⚡",
        "description": "MiniMax M2.7 frontier, Chinese vendor",
        "default_model": "MiniMax-M2.7",
        "default_url": "https://api.minimax.chat/v1",
        "needs_api_key": True,
    },
    "stepfun": {
        "name": "StepFun", "emoji": "👣",
        "description": "StepFun step-2 16k, Chinese open-weights",
        "default_model": "step-2-16k",
        "default_url": "https://api.stepfun.com/v1",
        "needs_api_key": True,
    },
    "doubao": {
        "name": "Doubao", "emoji": "🫘",
        "description": "ByteDance Doubao Pro 128k via Volcano",
        "default_model": "doubao-pro-128k",
        "default_url": "https://ark.cn-beijing.volces.com/api/v3",
        "needs_api_key": True,
    },
    "yi": {
        "name": "Yi (01.AI)", "emoji": "✴️",
        "description": "01.AI Yi Lightning, Chinese open-weights",
        "default_model": "yi-lightning",
        "default_url": "https://api.lingyiwanwu.com/v1",
        "needs_api_key": True,
    },
    "spark": {
        "name": "iFlytek Spark", "emoji": "✨",
        "description": "iFlytek Spark 4.0 Ultra, Chinese frontier",
        "default_model": "spark-4.0-ultra",
        "default_url": "https://spark-api.xf-yun.com/v1",
        "needs_api_key": True,
    },
    "openai": {
        "name": "OpenAI", "emoji": "🤖",
        "description": "OpenAI GPT-4o, GPT-4.1, o-series",
        "default_model": "gpt-4o",
        "default_url": "https://api.openai.com/v1",
        "needs_api_key": True,
    },
    "anthropic": {
        "name": "Anthropic", "emoji": "🧠",
        "description": "Claude 3.5/4 Sonnet, Opus, Haiku",
        "default_model": "claude-sonnet-4-20250514",
        "default_url": "https://api.anthropic.com/v1",
        "needs_api_key": True,
    },
    "google": {
        "name": "Google Gemini", "emoji": "💎",
        "description": "Gemini 2.5 Pro / Flash",
        "default_model": "gemini-2.5-pro-exp-03-25",
        "default_url": "https://generativelanguage.googleapis.com/v1beta",
        "needs_api_key": True,
    },
    "meta": {
        "name": "Meta Llama", "emoji": "🦙",
        "description": "Llama 4 Maverick via Together",
        "default_model": "meta-llama/Llama-4-Maverick-17B-128E",
        "default_url": "https://api.together.xyz/v1",
        "needs_api_key": True,
    },
    "mistral": {
        "name": "Mistral AI", "emoji": "🌪️",
        "description": "Mistral Large via OpenAI-compatible API",
        "default_model": "mistral-large-latest",
        "default_url": "https://api.mistral.ai/v1",
        "needs_api_key": True,
    },
    "cohere": {
        "name": "Cohere", "emoji": "🔗",
        "description": "Cohere Command R+",
        "default_model": "command-r-plus",
        "default_url": "https://api.cohere.ai/v1",
        "needs_api_key": True,
    },
    "xai": {
        "name": "xAI Grok", "emoji": "🚀",
        "description": "xAI Grok 3 — frontier model",
        "default_model": "grok-3-beta",
        "default_url": "https://api.x.ai/v1",
        "needs_api_key": True,
    },
    "reka": {
        "name": "Reka AI", "emoji": "🦜",
        "description": "Reka Core multimodal",
        "default_model": "reka-core",
        "default_url": "https://api.reka.ai/v1",
        "needs_api_key": True,
    },
    "perplexity": {
        "name": "Perplexity", "emoji": "🔍",
        "description": "Perplexity Sonar — search-augmented",
        "default_model": "sonar-pro",
        "default_url": "https://api.perplexity.ai/v1",
        "needs_api_key": True,
    },
    "openrouter": {
        "name": "OpenRouter", "emoji": "🌐",
        "description": "OpenRouter unified gateway",
        "default_model": "anthropic/claude-sonnet-4",
        "default_url": "https://openrouter.ai/api/v1",
        "needs_api_key": True,
    },
    "groq": {
        "name": "Groq", "emoji": "⚡",
        "description": "Groq ultra-fast Llama 3.3 70B",
        "default_model": "llama-3.3-70b-versatile",
        "default_url": "https://api.groq.com/openai/v1",
        "needs_api_key": True,
    },
    "together": {
        "name": "Together AI", "emoji": "🤝",
        "description": "Together AI open-weights hosting",
        "default_model": "meta-llama/Llama-4-Maverick-17B-128E",
        "default_url": "https://api.together.xyz/v1",
        "needs_api_key": True,
    },
    "fireworks": {
        "name": "Fireworks AI", "emoji": "🎆",
        "description": "Fireworks AI inference platform",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "default_url": "https://api.fireworks.ai/inference/v1",
        "needs_api_key": True,
    },
    "anyscale": {
        "name": "Anyscale", "emoji": "📊",
        "description": "Anyscale Endpoints",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "default_url": "https://api.endpoints.anyscale.com/v1",
        "needs_api_key": True,
    },
    "deepinfra": {
        "name": "DeepInfra", "emoji": "🏗️",
        "description": "DeepInfra serverless inference",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "default_url": "https://api.deepinfra.com/v1/openai",
        "needs_api_key": True,
    },
    "siliconflow": {
        "name": "SiliconFlow", "emoji": "🌊",
        "description": "SiliconFlow hosted DeepSeek V3 and others",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "default_url": "https://api.siliconflow.cn/v1",
        "needs_api_key": True,
    },
    "ollama": {
        "name": "Ollama", "emoji": "🖥️",
        "description": "Ollama — local model runner",
        "default_model": "llama3.2",
        "default_url": "http://localhost:11434/v1",
        "needs_api_key": False,
    },
    "lmstudio": {
        "name": "LM Studio", "emoji": "💻",
        "description": "LM Studio local OpenAI-compatible server",
        "default_model": "local-model",
        "default_url": "http://localhost:1234/v1",
        "needs_api_key": False,
    },
    "vllm": {
        "name": "vLLM", "emoji": "🏎️",
        "description": "vLLM local OpenAI-compatible server",
        "default_model": "default",
        "default_url": "http://localhost:8000/v1",
        "needs_api_key": False,
    },
    "llamacpp": {
        "name": "llama.cpp Server", "emoji": "🦙",
        "description": "llama.cpp server, OpenAI-compatible",
        "default_model": "local",
        "default_url": "http://localhost:8080/v1",
        "needs_api_key": False,
    },
    "custom": {
        "name": "Custom (OpenAI-compatible)", "emoji": "🔧",
        "description": "Any OpenAI-compatible endpoint — fill in URL and key",
        "default_model": "gpt-4o",
        "default_url": "https://your-api.com/v1",
        "needs_api_key": True,
    },
    "local": {
        "name": "Local (no URL)", "emoji": "🪫",
        "description": "Local stub for offline development",
        "default_model": "",
        "default_url": "",
        "needs_api_key": False,
    },
}


def provider_keys() -> list:
    """Return the registered provider keys in declaration order."""
    return list(AI_PROVIDERS.keys())


def provider_display(key: str) -> str:
    """Return `emoji name` string used in interactive menus."""
    info = AI_PROVIDERS.get(key, {})
    return f"{info.get('emoji', '▪️')} {info.get('name', key)}"


def provider_descriptions() -> list:
    """Return the description strings for every registered provider."""
    return [AI_PROVIDERS[k].get("description", "") for k in AI_PROVIDERS]


REASONING_LEVELS = (
    ("xhigh",   "xhigh   - maximum reasoning effort (slowest, deepest)"),
    ("high",    "high    - thorough reasoning (default for o-series)"),
    ("medium",  "medium  - balanced reasoning vs. latency"),
    ("low",     "low     - fast responses, light reasoning"),
    ("minimal", "minimal - near-zero reasoning overhead"),
    ("none",    "none    - disable reasoning entirely"),
)


REASONING_BY_PROVIDER = {
    "openai":     ("xhigh", "high", "medium", "low", "minimal"),
    "anthropic":  ("high", "medium", "low"),
    "google":     ("high", "medium", "low", "minimal", "none"),
    "deepseek":   ("high", "medium", "low", "none"),
    "moonshot":   ("medium", "low", "none"),
    "zhipu":      ("medium", "low", "none"),
    "baichuan":   ("medium", "low", "none"),
    "minimax":    ("high", "medium", "low"),
    "stepfun":    ("medium", "low", "none"),
    "doubao":     ("high", "medium", "low"),
    "yi":         ("medium", "low"),
    "spark":      ("medium", "low", "none"),
    "meta":       ("medium", "low", "none"),
    "mistral":    ("medium", "low", "none"),
    "cohere":     ("medium", "low", "none"),
    "groq":       ("medium", "low"),
    "xai":        ("xhigh", "high", "medium", "low"),
    "perplexity": ("medium", "low"),
    "openrouter": ("xhigh", "high", "medium", "low", "minimal", "none"),
}


def resolve_reasoning_level(provider_key, requested=None):
    """Return a reasoning-effort level valid for the given provider.

    Falls back to the provider's strongest advertised level when the
    requested one isn't supported, and to "medium" for unknown
    providers.
    """
    supported = REASONING_BY_PROVIDER.get(provider_key)
    if not supported:
        return requested or "medium"
    if requested in supported:
        return requested
    return supported[0]
