"""

"""

AI_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek", "emoji": "🔢",
        "default_model": "deepseek-chat",
        "default_url": "https://api.deepseek.com/v1",
        "needs_api_key": True
    },
    "qwen": {
        "default_model": "qwen-max",
        "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "needs_api_key": True
    },
    "zhipu": {
        "default_model": "glm-4-plus",
        "default_url": "https://open.bigmodel.cn/api/paas/v4",
        "needs_api_key": True
    },
    "moonshot": {
        "default_model": "moonshot-v1-128k",
        "default_url": "https://api.moonshot.cn/v1",
        "needs_api_key": True
    },
    "baichuan": {
        "default_model": "Baichuan4",
        "default_url": "https://api.baichuan-ai.com/v1",
        "needs_api_key": True
    },
    "minimax": {
        "name": "MiniMax", "emoji": "⚡",
        "default_model": "MiniMax-M2.7",
        "default_url": "https://api.minimax.chat/v1",
        "needs_api_key": True
    },
    "stepfun": {
        "default_model": "step-2-16k",
        "default_url": "https://api.stepfun.com/v1",
        "needs_api_key": True
    },
    "doubao": {
        "default_model": "doubao-pro-128k",
        "default_url": "https://ark.cn-beijing.volces.com/api/v3",
        "needs_api_key": True
    },
    "yi": {
        "default_model": "yi-lightning",
        "default_url": "https://api.lingyiwanwu.com/v1",
        "needs_api_key": True
    },
    "spark": {
        "default_model": "spark-4.0-ultra",
        "default_url": "https://spark-api.xf-yun.com/v1",
        "needs_api_key": True
    },
    "openai": {
        "name": "OpenAI", "emoji": "🤖",
        "default_model": "gpt-4o",
        "default_url": "https://api.openai.com/v1",
        "needs_api_key": True
    },
    "anthropic": {
        "name": "Anthropic", "emoji": "🧠",
        "description": "Claude 3.5/4 Sonnet, Opus, Haiku",
        "default_model": "claude-sonnet-4-20250514",
        "default_url": "https://api.anthropic.com/v1",
        "needs_api_key": True
    },
    "google": {
        "name": "Google Gemini", "emoji": "💎",
        "default_model": "gemini-2.5-pro-exp-03-25",
        "default_url": "https://generativelanguage.googleapis.com/v1beta",
        "needs_api_key": True
    },
    "meta": {
        "name": "Meta Llama", "emoji": "🦙",
        "default_model": "meta-llama/Llama-4-Maverick-17B-128E",
        "default_url": "https://api.together.xyz/v1",
        "needs_api_key": True
    },
    "mistral": {
        "name": "Mistral AI", "emoji": "🌪️",
        "default_model": "mistral-large-latest",
        "default_url": "https://api.mistral.ai/v1",
        "needs_api_key": True
    },
    "cohere": {
        "name": "Cohere", "emoji": "🔗",
        "default_model": "command-r-plus",
        "default_url": "https://api.cohere.ai/v1",
        "needs_api_key": True
    },
    "xai": {
        "name": "xAI Grok", "emoji": "🚀",
        "default_model": "grok-3-beta",
        "default_url": "https://api.x.ai/v1",
        "needs_api_key": True
    },
    "reka": {
        "name": "Reka AI", "emoji": "🦜",
        "default_model": "reka-core",
        "default_url": "https://api.reka.ai/v1",
        "needs_api_key": True
    },
    "perplexity": {
        "name": "Perplexity", "emoji": "🔍",
        "default_model": "sonar-pro",
        "default_url": "https://api.perplexity.ai/v1",
        "needs_api_key": True
    },
    "openrouter": {
        "name": "OpenRouter", "emoji": "🌐",
        "default_model": "anthropic/claude-sonnet-4",
        "default_url": "https://openrouter.ai/api/v1",
        "needs_api_key": True
    },
    "groq": {
        "name": "Groq", "emoji": "⚡",
        "default_model": "llama-3.3-70b-versatile",
        "default_url": "https://api.groq.com/openai/v1",
        "needs_api_key": True
    },
    "together": {
        "name": "Together AI", "emoji": "🤝",
        "default_model": "meta-llama/Llama-4-Maverick-17B-128E",
        "default_url": "https://api.together.xyz/v1",
        "needs_api_key": True
    },
    "fireworks": {
        "name": "Fireworks AI", "emoji": "🎆",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "default_url": "https://api.fireworks.ai/inference/v1",
        "needs_api_key": True
    },
    "anyscale": {
        "name": "Anyscale", "emoji": "📊",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "default_url": "https://api.endpoints.anyscale.com/v1",
        "needs_api_key": True
    },
    "deepinfra": {
        "name": "DeepInfra", "emoji": "🏗️",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "default_url": "https://api.deepinfra.com/v1/openai",
        "needs_api_key": True
    },
    "siliconflow": {
        "name": "SiliconFlow", "emoji": "🌊",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "default_url": "https://api.siliconflow.cn/v1",
        "needs_api_key": True
    },
    "ollama": {
        "name": "Ollama", "emoji": "🖥️",
        "default_model": "llama3.2",
        "default_url": "http://localhost:11434/v1",
        "needs_api_key": False
    },
    "lmstudio": {
        "name": "LM Studio", "emoji": "💻",
        "default_model": "local-model",
        "default_url": "http://localhost:1234/v1",
        "needs_api_key": False
    },
    "vllm": {
        "name": "vLLM", "emoji": "🏎️",
        "default_model": "default",
        "default_url": "http://localhost:8000/v1",
        "needs_api_key": False
    },
    "llamacpp": {
        "name": "llama.cpp Server", "emoji": "🦙",
        "default_model": "local",
        "default_url": "http://localhost:8080/v1",
        "needs_api_key": False
    },
    "custom": {
        "default_model": "gpt-4o",
        "default_url": "https://your-api.com/v1",
        "needs_api_key": True
    },
    "local": {
        "default_model": "",
        "default_url": "",
        "needs_api_key": False
    },
}
