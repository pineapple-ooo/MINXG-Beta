"""Scanner — walks a directory tree and extracts CapModule records.

minxg.cap.provides: cap.scan.file, cap.scan.tree
minxg.cap.requires: (none)
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterable, List, Optional

from .manifest import CapModule, PROVIDE_TAG, REQUIRE_TAG


_PROVIDE_RE = re.compile(r"(?m)^[ \t]*minxg\.cap\.provides\s*:\s*([^\n]+)")
_REQUIRE_RE = re.compile(r"(?m)^[ \t]*minxg\.cap\.requires\s*:\s*([^\n]+)")


def _parse_caps(raw: str) -> tuple:
    parts = [p.strip() for p in raw.split(",")]
    skip = {"", "(none)", "none", "n/a", "-"}
    return tuple(p for p in parts if p and p.lower() not in skip)


def scan_file(path: Path, *, content: Optional[str] = None, head_limit: int = 50) -> Optional[CapModule]:
    """Return a CapModule parsed from the given file, or None if no caps.

    Only the first `head_limit` lines are scanned. This keeps comments
    and inline examples later in the file from being treated as live
    capability declarations. The limit is intentionally small — capability
    markers belong at the top of the file, not deep inside examples.
    """
    if content is None:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
    head = "".join(content.splitlines(keepends=True)[:head_limit])
    provide_match = _PROVIDE_RE.search(head)
    require_match = _REQUIRE_RE.search(head)
    if not provide_match and not require_match:
        return None
    provides = _parse_caps(provide_match.group(1)) if provide_match else ()
    requires = _parse_caps(require_match.group(1)) if require_match else ()
    return CapModule(
        path=str(path),
        provides=provides,
        requires=requires,
    )


def scan_tree(root: Path, *, skip: Optional[Iterable[Path]] = None) -> List[CapModule]:
    """Scan a directory tree in-place, returning all discovered CapModule
    records in deterministic path order."""
    skip_set = set(skip or ())
    out: List[CapModule] = []
    if not root.exists():
        return out
    for path in sorted(root.rglob("*.py")):
        if any(part.startswith("__pycache__") or part.startswith(".") for part in path.parts):
            continue
        if path in skip_set:
            continue
        record = scan_file(path)
        if record is not None:
            out.append(record)
    return out
