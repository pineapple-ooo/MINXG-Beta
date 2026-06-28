"""minxg.contracts.runtime.manifest — single source of truth for adapters.

This is the JSON-equivalent table that the 0.14.0 polyglot feature
defers to. Every language adapter MINXG can dispatch to has one entry
here. The runtime discovery walks this table once and loads each
adapter module.

Note: this file is intentionally a Python dict rather than an external
JSON — that keeps the auto-discovery path self-contained at import
time, with no file-system dependency. Manifest JSON FILES (per-package)
live next to each adapter module in real deployments; this file is the
catalogue that lists them.
"""
from __future__ import annotations

from typing import Dict, List

POLYGLOT_LANGUAGES: List[str] = [
    "python",   # always-on, native Python ecosystem
    "cpp",      # C / C++ via libminxg_core / libminxg_c
    "go",       # Go shared libs — sys/IO/rate-limit
    "wasm",     # WebAssembly sandboxed compute (WASI)
    "r",        # R statistical + visualisation
    "datalog",  # Datalog logic programme for rules/queries
    "julia",    # Julia numerical / scientific
]

POLYGLOT_MANIFEST: Dict[str, Dict[str, str]] = {
    "python": {
        "name": "python",
        "version": "0.14.0",
        "status": "native",
        "module": "minxg.contracts.runtime.python",
    },
    "cpp": {
        "name": "cpp",
        "version": "0.14.0",
        "status": "compiled-stub",
        "module": "minxg.contracts.runtime.cpp",
    },
    "go": {
        "name": "go",
        "version": "0.14.0",
        "status": "compiled-stub",
        "module": "minxg.contracts.runtime.go",
    },
    "wasm": {
        "name": "wasm",
        "version": "0.14.0",
        "status": "stub",
        "module": "minxg.contracts.runtime.wasm",
    },
    "r": {
        "name": "r",
        "version": "0.14.0",
        "status": "stub",
        "module": "minxg.contracts.runtime.r",
    },
    "datalog": {
        "name": "datalog",
        "version": "0.14.0",
        "status": "stub",
        "module": "minxg.contracts.runtime.datalog",
    },
    "julia": {
        "name": "julia",
        "version": "0.14.0",
        "status": "stub",
        "module": "minxg.contracts.runtime.julia",
    },
}


def lang_info(lang: str) -> Dict[str, str]:
    """Look up one language entry, return defaults if missing."""
    return POLYGLOT_MANIFEST.get(
        lang.lower().strip(),
        {"name": lang, "version": "0.0.0", "status": "unknown",
         "module": ""},
    )


__all__ = ["POLYGLOT_LANGUAGES", "POLYGLOT_MANIFEST", "lang_info"]
