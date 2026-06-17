"""

"""

PLATFORMS = {
    "telegram": {
        "name": "Telegram",
        "emoji": "✈️",
        "fields": [
            {"name": "token", "label": "Bot Token", "description": "Get from @BotFather", "password": True}
        ],
    },
    "discord": {
        "name": "Discord",
        "emoji": "🎮",
        "fields": [
            {"name": "token", "label": "Bot Token", "description": "From Discord Developer Portal", "password": True}
        ],
    },
    "qq": {
        "emoji": "🐧",
        "fields": [
            {"name": "token", "label": "Token/Secret", "description": "QQ Bot Secret", "password": True}
        ],
    },
    "dingtalk": {
        "emoji": "📎",
        "fields": [
        ],
    },
    "feishu": {
        "emoji": "🐦",
        "fields": [
        ],
    },
    "slack": {
        "name": "Slack",
        "emoji": "💬",
        "fields": [
            {"name": "token", "label": "Bot Token (xoxb-...)", "description": "Slack App Bot User OAuth Token", "password": True}
        ],
    },
}

PLATFORM_ORDER = ["telegram", "discord", "qq", "dingtalk", "feishu", "slack"]
