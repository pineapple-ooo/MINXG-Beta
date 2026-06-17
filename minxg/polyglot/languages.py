"""Language detection."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional


_HEURISTICS = (
    ("rust", re.compile(r"\bfn\s+[a-zA-Z_][\w]*\s*\([^)]*\)\s*->|impl\s+|let\s+mut\s+|use\s+\w+::")),
    ("javascript", re.compile(r"\b(function\s+[a-zA-Z_]\w*\s*\(|const\s+[a-zA-Z_]\w*\s*=\s*\(|=>\s*\{|document\.|console\.|require\(|module\.exports)")),
    ("go", re.compile(r"\bpackage\s+\w+\b|\bfunc\s+[a-zA-Z_]\w*\s*\([^)]*\)|:=\s*|fmt\.Println|import\s*\(\s*\".+\"\s*\)")),
    ("shell", re.compile(r"^\s*#!.*(?:sh|bash)|\$\{?[A-Za-z_][\w]*\}?|\b(echo|grep|awk|sed)\s+")),
    ("python", re.compile(r"\bdef\s+[a-zA-Z_]\w*\s*\([^)]*\):|\bimport\s+\w+|\bclass\s+[A-Z]\w*\s*:|from\s+\w+\s+import\s+")),
)


def detect_language(text: str) -> str:
    best = ""
    best_hits = 0
    for lang, rx in _HEURISTICS:
        hits = len(rx.findall(text))
        if hits > best_hits:
            best_hits = hits
            best = lang
    return best or "unknown"


def detect_language_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".py": "python",
        ".rs": "rust",
        ".js": "javascript",
        ".ts": "javascript",
        ".go": "go",
        ".sh": "shell",
        ".bash": "shell",
    }.get(suffix, detect_language(path.read_text(encoding="utf-8") if path.exists() else ""))
