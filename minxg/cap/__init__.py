"""minxg.cap — Corpus-based Capability Registry.

Every MINXG module declares its capability surface in a docstring
header. `cap_manifest` reads those declarations across the live
tree and provides:

    * `what_provides(cap) -> list[str]` — paths to modules supplying a cap
    * `what_requires(cap) -> list[str]` — paths that break if a cap is lost
    * `dependencies_of(path) -> set[str]` — full closure of caps consumed
    * `changes_since(baseline) -> list[CapChange]` — for change-detection
    * `check() -> list[CapIssue]` — broken-cap chains for the current tree

Convention: put two markers at the top of each file (typically the
module docstring):

    marker 1: `minxg.cap.provides: <cap>[, <cap>, ...]`
    marker 2: `minxg.cap.requires: <cap>[, <cap>, ...]`

Omit `requires` for leaves. Both markers may be combined into a
single opening line: the parser treats each `cap.` tag separately.

This is the architectural answer to "I changed one module and three
others broke without my noticing."  The registry is human-readable,
built at import time, queryable from a one-liner terminal command
(`python -m minxg.cap <query>`).

NOT a plugin system.  NOT a name service.  Just an inventory that
survives rewrites because it lives in comment-bearing headers.
"""
from .manifest import (
    CapManifest, CapChange, CapIssue, CapModule,
    PROVIDE_TAG, REQUIRE_TAG,
)
from .scanner import scan_tree, scan_file
from .registry import get_manifest, reset_manifest, reindex
from .cli import main as cli_main

__all__ = [
    "CapManifest", "CapChange", "CapIssue", "CapModule",
    "PROVIDE_TAG", "REQUIRE_TAG",
    "scan_tree", "scan_file",
    "get_manifest", "reset_manifest", "reindex",
    "cli_main",
]
