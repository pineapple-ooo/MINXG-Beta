"""
minxg/text_tools.py - Text processing tools
Performance-critical operations delegated to C via core_native bridge.
"""
from __future__ import annotations
import difflib
import re
from typing import Dict, List

from minxg.base import BaseWorker, tool

_has_native = False
_slugify = _truncate = _extract_urls = _extract_emails = None
_extract_hashtags = _normalize_ws = _base_convert = _word_freq_hash = _tokenize = _trim = None

try:
    from .core_native import (
        slugify as _slugify,
        truncate as _truncate,
        extract_urls as _extract_urls,
        extract_emails as _extract_emails,
        extract_hashtags as _extract_hashtags,
        normalize_whitespace as _normalize_ws,
        base_convert as _base_convert,
        word_freq_hash as _word_freq_hash,
        word_frequency as _word_frequency_native,
        tokenize as _tokenize,
        trim as _trim,
    )
    _has_native = True
except (ImportError, OSError):
    pass


class TextToolsWorker(BaseWorker):
    facade_alias = "text_kit"
    worker_id = "text_tools"
    tier = "ai"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(description="Split text into words using optimized tokenizer", category="analyze")
    async def tokenize(self, text: str) -> Dict:
        if _has_native:
            try:
                tokens = _tokenize(text)
                return {"words": tokens, "count": len(tokens)}
            except Exception:
                pass
        words = re.findall(r"\b\w+\b", text.lower())
        return {"words": words, "count": len(words)}

    @tool(description="Count word frequencies in text (C-native hash table)", category="analyze")
    async def word_frequency(self, text: str, top: int = 20) -> Dict:
        if _has_native:
            try:
                pairs = _word_freq_hash(text, top)
                top_items = dict(pairs)
                return {"frequencies": top_items, "total_unique": len(pairs)}
            except Exception:
                pass
        words = re.findall(r"\b\w+\b", text.lower())
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        top_items = dict(sorted(freq.items(), key=lambda x: -x[1])[:top])
        return {"frequencies": top_items, "total_unique": len(freq)}

    @tool(description="Trim whitespace from text (C optimized)", category="transform")
    async def trim(self, text: str) -> Dict:
        if _has_native:
            try:
                result = _trim(text)
                return {"text": result, "original_length": len(text), "trimmed_length": len(result)}
            except Exception:
                pass
        return {"text": text.strip(), "original_length": len(text), "trimmed_length": len(text.strip())}

    @tool(description="Truncate text to max_length with suffix (C-native)", category="transform")
    async def truncate(self, text: str, max_length: int = 100, suffix: str = "...") -> Dict:
        if _has_native:
            try:
                result = _truncate(text, max_length, suffix)
                return {"text": result, "truncated": len(result) < len(text), "original_length": len(text), "length": len(result)}
            except Exception:
                pass
        if len(text) <= max_length:
            return {"text": text, "truncated": False, "length": len(text)}
        truncated = text[:max_length - len(suffix)] + suffix
        return {"text": truncated, "truncated": True, "original_length": len(text), "length": len(truncated)}

    @tool(description="Count words, sentences, characters, lines", category="analyze")
    async def word_count(self, text: str) -> Dict:
        words = len(text.split())
        sentences = len([s for s in re.split(r"[.!?]", text) if s.strip()])
        return {"words": words, "sentences": sentences, "chars": len(text), "lines": text.count("\n") + 1}

    @tool(description="Generate URL-friendly slug (C-native)", category="transform")
    async def slugify(self, text: str) -> Dict:
        if _has_native:
            try:
                return {"slug": _slugify(text), "original": text}
            except Exception:
                pass
        s = text.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[-\s]+", "-", s)
        return {"slug": s, "original": text}

    @tool(description="Estimate token count (4 chars per token for English)", category="analyze")
    async def token_estimate(self, text: str) -> Dict:
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(text) - chinese_chars
        tokens = chinese_chars + max(1, other_chars // 4)
        return {"estimated_tokens": tokens, "chinese_chars": chinese_chars, "other_chars": other_chars}

    @tool(description="Generate unified diff between two texts", category="analyze")
    async def text_diff(self, old: str, new: str, context: int = 3) -> Dict:
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=context))
        return {
            "diff": "".join(diff),
            "changes": len(diff),
            "added": sum(1 for l in diff if l.startswith("+")),
            "removed": sum(1 for l in diff if l.startswith("-")),
        }

    @tool(description="Wrap text to specified width", category="transform")
    async def text_wrap(self, text: str, width: int = 80) -> Dict:
        import textwrap
        wrapped = textwrap.fill(text, width=width)
        return {"wrapped": wrapped, "width": width, "lines": wrapped.count("\n") + 1}

    @tool(description="Extract all URLs from text (C-native)", category="extract")
    async def extract_urls(self, text: str) -> Dict:
        if _has_native:
            try:
                urls = _extract_urls(text)
                return {"count": len(urls), "urls": urls}
            except Exception:
                pass
        pattern = r"https?://[^\s<>\"`{}|\\^\[\]]+"
        urls = re.findall(pattern, text)
        return {"count": len(urls), "urls": urls}

    @tool(description="Extract all email addresses from text (C-native)", category="extract")
    async def extract_emails(self, text: str) -> Dict:
        if _has_native:
            try:
                emails = _extract_emails(text)
                return {"count": len(emails), "emails": emails}
            except Exception:
                pass
        pattern = r"[\w.-]+@[\w.-]+\.\w+"
        emails = re.findall(pattern, text)
        return {"count": len(emails), "emails": emails}

    @tool(description="Normalize whitespace (C-native)", category="transform")
    async def normalize_whitespace(self, text: str, line_ending: str = "\n") -> Dict:
        if _has_native:
            try:
                t = _normalize_ws(text, line_ending)
                return {"text": t, "original_length": len(text), "new_length": len(t)}
            except Exception:
                pass
        t = text.strip()
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\r\n|\r|\n", line_ending, t)
        return {"text": t, "original_length": len(text), "new_length": len(t)}