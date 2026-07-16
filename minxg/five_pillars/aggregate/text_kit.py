"""minxg/five_pillars/aggregate/text_kit.py - unified text facade.

Why this file exists
--------------------
The legacy ``text_tools.py`` exposed 12 ``@tool`` methods. ``string_tools.py``
exposed 8 with overlapping semantics. ``text_adv.py`` exposed ~80 more.
Each was a one-shot pure-Python job. The aggregate: ~100 tool entries
visible to every AI agent.

This file collapses those into **2 tools**: ``text_op`` (dispatch) and
``text_op_list`` (discovery). The legacy worker modules are kept for
backward compatibility - any test or existing code still binds through
them unchanged.

Design rules
------------
1. **Do not remove old workers.** Renaming or deleting them would break
   existing callers; we are adding a parallel superstructure.
2. **Discovery is a first-class tool.** AI agents can ask "what can
   text_op do?" without scrolling the full schema.
3. **Idempotent payloads.** Every op signature is keyword-only; the
   dispatch table is the single source of truth for arg defaults.
4. **Optional C backend.** Pure-Python reference implementation; the
   ``core_native`` bridge is consulted when available as a fast path.
"""
from __future__ import annotations

import re
import difflib

from typing import Any, Callable, Dict, List

from minxg.base import BaseWorker, tool


# ── Native fast-path adapter (lazy) ────────────────────────────────────────────
import sys as _sys

_native: Dict[str, Any] = {}
_mod = _sys.modules.get("minxg.five_pillars.scalar.core_native")
if _mod is not None:
    for k in ("slugify", "truncate", "extract_urls", "extract_emails",
              "extract_hashtags", "normalize_whitespace",
              "word_freq_hash", "tokenize", "trim", "word_frequency"):
        fn = getattr(_mod, k, None)
        if callable(fn):
            _native[k] = fn

_NATIVE_KEY = {
    "slugify": "slugify", "truncate": "truncate",
    "extract_urls": "extract_urls", "extract_emails": "extract_emails",
    "extract_hashtags": "extract_hashtags",
    "normalize_whitespace": "normalize_whitespace",
    "word_frequency": "word_freq_hash",
    "tokenize": "tokenize", "trim": "trim",
}


def _n(op_key, *args):
    fn = _native.get(_NATIVE_KEY.get(op_key, op_key))
    if not fn:
        return _MISS
    try:
        return fn(*args)
    except Exception:
        return _MISS


_MISS = object()


# ── Pure-Python ops (one helper per op, all return dicts) ─────────────────────

def _slugify(text=""):
    if (r := _n("slugify", text)) is not _MISS:
        return {"slug": r, "original": text}
    s = re.sub(r"[^\w\s-]", "", (text or "").lower().strip())
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return {"slug": s, "original": text}


def _truncate(text="", max_length=100, suffix="..."):
    if (r := _n("truncate", text, max_length, suffix)) is not _MISS:
        return {"text": r, "truncated": len(r) < len(text or ""),
                "length": len(r), "original_length": len(text or "")}
    t = text or ""
    if len(t) <= max_length:
        return {"text": t, "truncated": False, "length": len(t)}
    out = t[: max_length - len(suffix)] + suffix
    return {"text": out, "truncated": True, "length": len(out),
            "original_length": len(t)}


def _trim(text=""):
    if (r := _n("trim", text)) is not _MISS:
        return {"text": r, "original_length": len(text or ""),
                "trimmed_length": len(r)}
    t = (text or "").strip()
    return {"text": t, "original_length": len(text or ""),
            "trimmed_length": len(t)}


def _tokenize(text=""):
    if (r := _n("tokenize", text)) is not _MISS:
        return {"words": r, "count": len(r)}
    return {"words": re.findall(r"\b\w+\b", (text or "").lower()), "count": 0}


def _word_frequency(text="", top=20):
    if (r := _n("word_frequency", text, top)) is not _MISS:
        items = dict(r)
        return {"frequencies": items, "total_unique": len(r)}
    words = re.findall(r"\b\w+\b", (text or "").lower())
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    items = dict(sorted(freq.items(), key=lambda x: -x[1])[:top])
    return {"frequencies": items, "total_unique": len(freq)}


def _word_count(text=""):
    t = text or ""
    return {"words": len(t.split()),
            "sentences": len([s for s in re.split(r"[.!?]", t) if s.strip()]),
            "chars": len(t), "lines": t.count("\n") + 1}


def _token_estimate(text=""):
    t = text or ""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", t))
    other_chars = len(t) - chinese_chars
    return {"estimated_tokens": chinese_chars + max(1, other_chars // 4),
            "chinese_chars": chinese_chars, "other_chars": other_chars}


def _text_diff(old="", new="", context=3):
    diff = list(difflib.unified_diff(
        (old or "").splitlines(keepends=True),
        (new or "").splitlines(keepends=True), lineterm="", n=context))
    return {"diff": "".join(diff), "changes": len(diff),
            "added": sum(1 for l in diff if l.startswith("+")),
            "removed": sum(1 for l in diff if l.startswith("-"))}


def _text_wrap(text="", width=80):
    import textwrap
    wrapped = textwrap.fill(text or "", width=width)
    return {"wrapped": wrapped, "width": width,
            "lines": wrapped.count("\n") + 1}


def _extract_urls(text=""):
    if (r := _n("extract_urls", text)) is not _MISS:
        return {"count": len(r), "urls": r}
    urls = re.findall(r"https?://[^\s<>\"`{}|\\^\[\]]+", text or "")
    return {"count": len(urls), "urls": urls}


def _extract_emails(text=""):
    if (r := _n("extract_emails", text)) is not _MISS:
        return {"count": len(r), "emails": r}
    emails = re.findall(r"[\w.-]+@[\w.-]+\.\w+", text or "")
    return {"count": len(emails), "emails": emails}


def _extract_hashtags(text=""):
    if (r := _n("extract_hashtags", text)) is not _MISS:
        return {"count": len(r), "hashtags": r}
    return {"count": len(r := re.findall(r"#(\w+)", text or "")),
            "hashtags": r}


def _extract_mentions(text=""):
    m = re.findall(r"@(\w+)", text or "")
    return {"count": len(m), "mentions": m}


def _extract_numbers(text=""):
    nums = re.findall(r"-?\d+\.?\d*", text or "")
    return {"count": len(nums),
            "numbers": [float(n) if "." in n else int(n) for n in nums]}


def _normalize_whitespace(text="", line_ending="\n"):
    if (r := _n("normalize_whitespace", text, line_ending)) is not _MISS:
        return {"text": r, "original_length": len(text or ""), "new_length": len(r)}
    t = re.sub(r"\r\n|\r|\n", line_ending, re.sub(r"[ \t]+", " ", (text or "").strip()))
    return {"text": t, "original_length": len(text or ""), "new_length": len(t)}


def _levenshtein(a="", b=""):
    a, b = a or "", b or ""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return {"distance": len(a)}
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1,
                             prev[j - 1] + (ca != cb)))
        prev = curr
    return {"distance": prev[-1]}


def _jaro_winkler(a="", b=""):
    a, b = a or "", b or ""
    if a == b:
        return {"similarity": 1.0}
    if not a or not b:
        return {"similarity": 0.0}
    md = max(len(a), len(b)) // 2 - 1
    md = max(0, md)
    am = [False] * len(a); bm = [False] * len(b)
    m = 0; t = 0
    for i, ca in enumerate(a):
        for j in range(max(0, i - md), min(i + md + 1, len(b))):
            if not bm[j] and ca == b[j]:
                am[i] = bm[j] = True; m += 1; break
    if m == 0:
        return {"similarity": 0.0}
    k = 0
    for i in range(len(a)):
        if am[i]:
            while not bm[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t //= 2
    j = (m / len(a) + m / len(b) + (m - t) / m) / 3
    p = 0
    for i in range(min(4, len(a), len(b))):
        if a[i] == b[i]:
            p += 1
        else:
            break
    return {"similarity": j + p * 0.1 * (1 - j)}


def _similarity(a="", b=""):
    # Pure-Python SequenceMatcher equivalent - keeps the legacy
    # ``tools.text_adv.similarity_ratio`` output shape.
    a, b = a or "", b or ""
    if not a and not b:
        return {"ratio": 1.0}
    if not a or not b:
        return {"ratio": 0.0}
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return {"ratio": 0.0}
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    lcs = 0
    for i, ca in enumerate(a):
        for j, cb in enumerate(b):
            if ca == cb:
                v = dp[i][j] + 1
                dp[i + 1][j + 1] = v
                if v > lcs:
                    lcs = v
    return {"ratio": 2.0 * lcs / (n + m)}


def _camel_to_snake(text=""):
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text or "")
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return {"result": s.lower(), "original": text}


def _snake_to_camel(text="", capitalize_first=False):
    parts = (text or "").split("_")
    if not parts:
        return {"result": "", "original": text}
    body = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    if capitalize_first and body:
        body = body[:1].upper() + body[1:]
    return {"result": body, "original": text}


def _regex_match(pattern="", text=""):
    try:
        m = re.match(pattern or "", text or "")
    except re.error as exc:
        return {"status": "error", "error": str(exc)}
    return {"matched": m.group(0) if m else None,
            "groups": list(m.groups()) if m else None}


def _regex_findall(pattern="", text=""):
    try:
        matches = re.findall(pattern or "", text or "")
    except re.error as exc:
        return {"status": "error", "error": str(exc)}
    return {"matches": matches, "count": len(matches)}


def _regex_replace(pattern="", text="", replacement=""):
    try:
        result, n = re.subn(pattern or "", replacement, text or "")
    except re.error as exc:
        return {"status": "error", "error": str(exc)}
    return {"result": result, "replacements": n}


def _html_escape(text=""):
    return {"result": (text or "")
            .replace("&", "&")
            .replace("<", "<")
            .replace(">", ">")
            .replace('"', '"')
            .replace("'", "'")}


def _json_escape(text=""):
    t = text or ""
    return {"result": (t.replace("\\", "\\\\")
                       .replace('"', '\\"')
                       .replace("\n", "\\n")
                       .replace("\r", "\\r")
                       .replace("\t", "\\t"))}


def _slug_safe(text=""):
    return _slugify(text)


# ── Route table: name → {fn, args, category, summary} ────────────────────────

_ROUTES: Dict[str, Dict[str, Any]] = {
    # text_tools.py routes (12)
    "tokenize": {"fn": _tokenize, "args": ["text"], "category": "analyze",
                 "summary": "split text into words"},
    "word_frequency": {"fn": _word_frequency, "args": ["text", "top=20"],
                       "category": "analyze",
                       "summary": "count word frequencies (top N)"},
    "trim": {"fn": _trim, "args": ["text"], "category": "transform",
             "summary": "strip whitespace"},
    "truncate": {"fn": _truncate, "args": ["text", "max_length=100", 'suffix="..."'],
                 "category": "transform", "summary": "truncate with suffix"},
    "word_count": {"fn": _word_count, "args": ["text"], "category": "analyze",
                   "summary": "count words / sentences / chars / lines"},
    "slugify": {"fn": _slugify, "args": ["text"], "category": "transform",
                "summary": "make URL-friendly slug"},
    "token_estimate": {"fn": _token_estimate, "args": ["text"],
                       "category": "analyze",
                       "summary": "estimate LLM tokens (CN + EN heuristic)"},
    "text_diff": {"fn": _text_diff, "args": ["old", "new", "context=3"],
                   "category": "analyze", "summary": "unified diff"},
    "text_wrap": {"fn": _text_wrap, "args": ["text", "width=80"],
                  "category": "transform", "summary": "wrap to width"},
    "extract_urls": {"fn": _extract_urls, "args": ["text"],
                     "category": "extract", "summary": "list all URLs"},
    "extract_emails": {"fn": _extract_emails, "args": ["text"],
                       "category": "extract", "summary": "list all emails"},
    "extract_hashtags": {"fn": _extract_hashtags, "args": ["text"],
                         "category": "extract", "summary": "list all #tags"},
    "extract_mentions": {"fn": _extract_mentions, "args": ["text"],
                         "category": "extract", "summary": "list all @mentions"},
    "extract_numbers": {"fn": _extract_numbers, "args": ["text"],
                        "category": "extract", "summary": "list all numeric tokens"},
    "normalize_whitespace": {"fn": _normalize_whitespace,
                             "args": ["text", "line_ending='\\n'"],
                             "category": "transform",
                             "summary": "normalise whitespace + line endings"},

    # similarity / diff metrics (text_adv routes)
    "levenshtein": {"fn": _levenshtein, "args": ["a", "b"],
                    "category": "similarity",
                    "summary": "Levenshtein edit distance"},
    "jaro_winkler": {"fn": _jaro_winkler, "args": ["a", "b"],
                     "category": "similarity",
                     "summary": "Jaro-Winkler similarity ratio (0..1)"},
    "similarity": {"fn": _similarity, "args": ["a", "b"],
                   "category": "similarity",
                   "summary": "SequenceMatcher ratio (2*lcs/(n+m))"},

    # regex ops
    "regex_match": {"fn": _regex_match, "args": ["pattern", "text"],
                    "category": "regex", "summary": "re.match single"},
    "regex_findall": {"fn": _regex_findall, "args": ["pattern", "text"],
                      "category": "regex", "summary": "re.findall all matches"},
    "regex_replace": {"fn": _regex_replace,
                      "args": ["pattern", "text", "replacement"],
                      "category": "regex", "summary": "re.sub replace"},

    # case converters
    "camel_to_snake": {"fn": _camel_to_snake, "args": ["text"],
                       "category": "format",
                       "summary": "camelCase → snake_case"},
    "snake_to_camel": {"fn": _snake_to_camel,
                       "args": ["text", "capitalize_first=False"],
                       "category": "format",
                       "summary": "snake_case → camelCase"},

    # escaping
    "html_escape": {"fn": _html_escape, "args": ["text"],
                    "category": "escape",
                    "summary": "escape HTML special chars"},
    "json_escape": {"fn": _json_escape, "args": ["text"],
                    "category": "escape",
                    "summary": "escape a string for JSON encoding"},
}


class TextKitWorker(BaseWorker):
    """One worker, many ops."""

    worker_id = "text_kit"
    tier = "ai"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(
        description=(
            "Run any text-processing op from the unified text_kit facade. "
            "Pass `op` to pick which - see `text_op_list` for the catalogue. "
            "Examples: op=slugify + text='Hello World!'; "
            "op=levenshtein + a=kitten + b=sitting."
        ),
        category="text",
    )
    async def text_op(self, op: str = "", **kwargs: Any) -> Dict:
        spec = _ROUTES.get(op)
        if spec is None:
            return {"status": "error",
                    "error": f"unknown op {op!r}; call text_op_list()",
                    "available": sorted(_ROUTES)}
        try:
            return spec["fn"](**kwargs)
        except Exception as exc:
            return {"status": "error", "op": op, "error": repr(exc)}

    @tool(
        description=(
            "List every op available in text_kit. The list is "
            "category-grouped and compact: collapsed from the ~100 "
            "text tools that existed before the facade. Call this "
            "when you're not sure which op a task maps to."
        ),
        category="text",
    )
    async def text_op_list(self) -> Dict:
        out: Dict[str, List[Dict[str, Any]]] = {}
        for name, spec in _ROUTES.items():
            cat = spec["category"]
            out.setdefault(cat, []).append({
                "op": name, "args": spec["args"],
                "summary": spec["summary"]})
        return {"categories": out, "total_ops": len(_ROUTES),
                "native_backend": bool(_native)}