"""Platform and provider config templates."""
import json, yaml

PROVIDER_TEMPLATE = yaml.dump({
    "openai": {"base_url":"https://api.openai.com/v1","models":["gpt-4o","gpt-4o-mini"]},
    "deepseek": {"base_url":"https://api.deepseek.com/v1","models":["deepseek-chat"]},
    "qwen": {"base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1","models":["qwen-max"]},
    "claude": {"base_url":"https://api.anthropic.com/v1","models":["claude-3-5-sonnet"]},
    "gemini": {"base_url":"https://generativelanguage.googleapis.com/v1beta","models":["gemini-2.0-flash"]},
    "local": {"base_url":"http://localhost:11434/v1","models":["llama3"]},
})

PLATFORM_TEMPLATE = yaml.dump({
    "telegram": {"token":"","enabled":False,"chat_ids":[]},
    "discord": {"token":"","enabled":False,"channel_ids":[]},
    "qq": {"app_id":"","token":"","enabled":False},
    "dingtalk": {"app_key":"","app_secret":"","enabled":False},
    "feishu": {"app_id":"","app_secret":"","enabled":False},
    "slack": {"token":"","enabled":False,"channels":[]},
})
