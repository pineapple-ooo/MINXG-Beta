"""Internationalization tools — language detection, translation helpers."""
from minxg.base import BaseWorker, tool

class I18nWorker(BaseWorker):
    facade_alias = "i18n_worker"
    worker_id = "i18n_worker"
    tier = "ai"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool
    async def detect_language(self, text: str = "") -> dict:
        """Detect the language of input text."""
        import re
        patterns = {
            "zh": (r"[\u4e00-\u9fff]", "Chinese"),
            "ja": (r"[\u3040-\u309f\u30a0-\u30ff]", "Japanese"),
            "ko": (r"[\uac00-\ud7af]", "Korean"),
            "ar": (r"[\u0600-\u06ff]", "Arabic"),
            "hi": (r"[\u0900-\u097f]", "Hindi"),
            "th": (r"[\u0e00-\u0e7f]", "Thai"),
            "ru": (r"[\u0400-\u04ff]", "Russian"),
        }
        for code, (pattern, name) in patterns.items():
            if re.search(pattern, text):
                return {"language": name, "code": code, "confidence": "high"}
        return {"language": "Unknown (Latin script)", "code": "en", "confidence": "low"}

    @tool
    async def language_list(self) -> dict:
        """List all 15 supported languages in MINXG."""
        return {"languages": [
            {"code":"en","name":"English","flag":"🇬🇧"},
            {"code":"ko","name":"한국어","flag":"🇰🇷"},
            {"code":"fr","name":"Français","flag":"🇫🇷"},
            {"code":"de","name":"Deutsch","flag":"🇩🇪"},
            {"code":"es","name":"Español","flag":"🇪🇸"},
            {"code":"pt-BR","name":"Português","flag":"🇧🇷"},
            {"code":"ru","name":"Русский","flag":"🇷🇺"},
            {"code":"ar","name":"العربية","flag":"🇸🇦"},
            {"code":"hi","name":"हिन्दी","flag":"🇮🇳"},
            {"code":"th","name":"ไทย","flag":"🇹🇭"},
            {"code":"vi","name":"Tiếng Việt","flag":"🇻🇳"},
            {"code":"id","name":"Bahasa Indonesia","flag":"🇮🇩"},
        ], "count": 15}

    @tool
    async def emoji_for_keyword(self, keyword: str = "") -> dict:
        """Get relevant emoji for a keyword."""
        emoji_map = {
            "file": "📄", "folder": "📁", "search": "🔍", "download": "⬇️",
            "upload": "⬆️", "delete": "🗑️", "edit": "✏️", "save": "💾",
            "error": "❌", "success": "✅", "warning": "⚠️", "info": "ℹ️",
            "lock": "🔒", "unlock": "🔓", "key": "🔑", "shield": "🛡️",
            "network": "🌐", "wifi": "📶", "bluetooth": "🔵", "battery": "🔋",
            "cpu": "💻", "memory": "🧠", "disk": "💿", "gpu": "🎮",
            "user": "👤", "robot": "🤖", "settings": "⚙️", "tools": "🔧",
            "code": "💻", "bug": "🐛", "test": "🧪", "build": "🔨",
            "time": "⏰", "date": "📅", "calendar": "🗓️", "clock": "🕐",
        }
        k = keyword.lower().strip()
        return {"keyword": keyword, "emoji": emoji_map.get(k, "•")}

    @tool
    async def format_number(self, number: float = 0, locale: str = "en") -> dict:
        """Format a number with locale-specific separators."""
        if locale in ("zh-CN","zh-TW","ja","ko"):
            s = f"{number:,.0f}" if number == int(number) else f"{number:,.2f}"
        else:
            s = f"{number:,.0f}" if number == int(number) else f"{number:,.2f}"
        return {"formatted": s, "locale": locale}

    @tool
    async def timezone_info(self) -> dict:
        """Get timezone information."""
        import time
        tz = time.tzname if hasattr(time, 'tzname') else ("UTC","UTC")
        offset = -(time.timezone / 3600) if time.daylight == 0 else -(time.altzone / 3600)
        return {"timezone": tz[0], "utc_offset": f"UTC{offset:+.0f}"}

    @tool
    async def date_localized(self, locale: str = "en") -> dict:
        """Get current date in localized format."""
        from datetime import datetime
        now = datetime.now()
        formats = {
            "en": now.strftime("%B %d, %Y"),
            "ko": now.strftime("%Y년 %m월 %d일"),
        }
        return {"date": formats.get(locale, now.isoformat()[:10]), "locale": locale, "iso": now.isoformat()}
