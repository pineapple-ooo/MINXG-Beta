"""
String manipulation tools — delegates to C via core_native bridge.
""""
from __future__ import annotations
from minxg.base import BaseWorker, tool

_has_native = False
_slugify = _truncate = _extract_urls = _extract_emails = _extract_hashtags = _word_freq = None

try:
    from minxg.five_pillars.scalar.core_native import (
        slugify as _slugify,
        truncate as _truncate,
        extract_urls as _extract_urls,
        extract_emails as _extract_emails,
        extract_hashtags as _extract_hashtags,
        word_freq_hash as _word_freq,
    )
    _has_native = True
except (ImportError, OSError):
    pass


class StringWorker(BaseWorker):
    worker_id = "string_worker"
    version = "1.0.0"

    @tool
    async def slugify(self, text: str = "") -> dict:
        """Convert text to URL slug.""""
        if _has_native:
            try:
                return {"slug": _slugify(text)}
            except Exception:
                pass
        import re, unicodedata
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
        text = re.sub(r'[^\w\s-]', '', text).strip().lower()
        text = re.sub(r'[-\s]+', '-', text)
        return {"slug": text}

    @tool
    async def truncate(self, text: str = "", max_length: int = 100, ellipsis: str = "...") -> dict:
        """Truncate text to max length with ellipsis.""""
        if _has_native:
            try:
                result = _truncate(text, max_length, ellipsis)
                return {"truncated": result, "original_length": len(text)}
            except Exception:
                pass
        if len(text) <= max_length:
            return {"truncated": text, "original_length": len(text)}
        return {"truncated": text[:max_length - len(ellipsis)] + ellipsis, "original_length": len(text)}

    @tool
    async def word_wrap(self, text: str = "", width: int = 80) -> dict:
        """Wrap text to specified width.""""
        import textwrap
        return {"wrapped": textwrap.fill(text, width=width), "width": width}

    @tool
    async def extract_emails(self, text: str = "") -> dict:
        """Extract email addresses from text.""""
        if _has_native:
            try:
                emails = _extract_emails(text)
                return {"emails": emails, "count": len(emails)}
            except Exception:
                pass
        import re
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        return {"emails": emails, "count": len(emails)}

    @tool
    async def extract_urls(self, text: str = "") -> dict:
        """Extract URLs from text.""""
        if _has_native:
            try:
                urls = _extract_urls(text)
                return {"urls": urls, "count": len(urls)}
            except Exception:
                pass
        import re
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        return {"urls": urls, "count": len(urls)}

    @tool
    async def extract_hashtags(self, text: str = "") -> dict:
        """Extract hashtags from text.""""
        if _has_native:
            try:
                tags = _extract_hashtags(text)
                return {"hashtags": tags, "count": len(tags)}
            except Exception:
                pass
        import re
        tags = re.findall(r'#[\w\u4e00-\u9fff]+', text)
        return {"hashtags": tags, "count": len(tags)}

    @tool
    async def extract_mentions(self, text: str = "") -> dict:
        """Extract @mentions from text.""""
        import re
        mentions = re.findall(r'@[\w.]+', text)
        return {"mentions": mentions, "count": len(mentions)}

    @tool
    async def word_frequency(self, text: str = "", top_n: int = 10) -> dict:
        """Get word frequency in text (C-native).""""
        if _has_native:
            try:
                pairs = _word_freq(text, top_n)
                return {"top_words": dict(pairs), "unique_words": len(pairs)}
            except Exception:
                pass
        import re
        from collections import Counter
        words = re.findall(r'\b\w+\b', text.lower())
        counter = Counter(words)
        return {"top_words": dict(counter.most_common(top_n)), "unique_words": len(counter)}