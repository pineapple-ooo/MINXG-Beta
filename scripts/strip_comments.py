"""Strip # inline comments from .py files while preserving docstrings and strings.

State-machine approach so we don't break:
  * triple-quoted strings (including docstrings and triple-quoted f-strings)
  * single-quoted strings with embedded '#'
  * hash characters inside expression continuations
"""
from __future__ import annotations
import io
import sys
from pathlib import Path


def strip_inline(source: str) -> tuple[str, int]:
    out = io.StringIO()
    i, n = 0, len(source)
    in_single = ""
    in_triple = ""
    removed = 0

    while i < n:
        if in_triple:
            if source.startswith(in_triple, i):
                out.write(in_triple)
                i += 3
                in_triple = ""
                continue
            out.write(source[i])
            i += 1
            continue

        if in_single:
            out.write(source[i])
            if source[i] == "\\" and i + 1 < n:
                out.write(source[i + 1])
                i += 2
                continue
            if source[i] == in_single:
                in_single = ""
            i += 1
            continue

        if source[i] == "#":
            removed += 1
            while i < n and source[i] != "\n":
                i += 1
            continue

        if source.startswith('"""', i) or source.startswith("'''", i):
            tq = source[i:i + 3]
            out.write(tq)
            i += 3
            in_triple = tq
            continue

        if source[i] in ("'", '"'):
            in_single = source[i]
            out.write(source[i])
            i += 1
            continue

        out.write(source[i])
        i += 1

    return out.getvalue(), removed


def main(root: Path) -> int:
    total_removed = 0
    files = 0
    for fp in root.rglob("*.py"):
        if not fp.is_file():
            continue
        parts = fp.parts
        if ".git" in parts or "_legacy" in parts or "build" in parts:
            continue
        original = fp.read_text(encoding="utf-8")
        stripped, removed = strip_inline(original)
        if stripped != original:
            fp.write_text(stripped, encoding="utf-8")
            total_removed += removed
            files += 1
    print(f"stripped {total_removed} comments from {files} files under {root}")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.exit(main(target))
