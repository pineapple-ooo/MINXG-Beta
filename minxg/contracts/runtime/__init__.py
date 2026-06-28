"""minxg.contracts.runtime — multi-language adapter surface (0.14.0).

Why this package exists
-----------------------
Earlier versions of MINXG had hard-coded language disaggregation spread
across ``minxg.polyglot`` (Python only) and ad-hoc ``subprocess.run``
calls into C / Go binaries. There was no consistent way to ask "what
languages are wired up, and at what version?" without grepping.

This package is the 0.14.0 answer. Every language MINXG can dispatch to
is an *adapter* under this package:

  - minxg.contracts.runtime.python     the Python ecosystem (default)
  - minxg.contracts.runtime.cpp        native C / C++ via system compiler
  - minxg.contracts.runtime.go         Go ``go run`` snippets
  - minxg.contracts.runtime.wasm       WebAssembly sandboxed compute
  - minxg.contracts.runtime.r          R statistical / visual computing
  - minxg.contracts.runtime.datalog    Datalog logic / rule reasoning
  - minxg.contracts.runtime.julia      Julia numerical / scientific

Each adapter module exposes ``ADAPTER_NAME``, ``ADAPTER_VERSION`` and
``ADAPTER_STATUS`` constants, plus an ``invoke(payload)`` entry point.
The shared ``minxg.contracts.runtime._exec`` helpers handle subprocess
probing (``which`` / ``run``) so every adapter degrades cleanly when its
runtime is not installed. The discovery entry point ``load`` plus the
manifest table in ``manifest.py`` give every adapter a single readable
name+version surface.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .manifest import POLYGLOT_LANGUAGES, POLYGLOT_MANIFEST  # noqa: F401

# ``installer`` is its own module, but the high-value surface
# (detect / plan / render_install_plan / platform_id) is also
# re-exported here so callers only ever import a single package.
from .installer import (  # noqa: F401  (re-export)
    InstallPlan,
    RuntimeStatus,
    MANAGED_LANGUAGES,
    detect_runtime,
    plan_install,
    current_plan,
    render_install_plan,
    run_install,
    status_snapshot,
    platform_id,
)

__all__ = [
    "POLYGLOT_LANGUAGES",
    "POLYGLOT_MANIFEST",
    "Adapter",
    "list_adapters",
    "load",
    "InstallPlan",
    "RuntimeStatus",
    "MANAGED_LANGUAGES",
    "detect_runtime",
    "plan_install",
    "current_plan",
    "render_install_plan",
    "run_install",
    "status_snapshot",
    "platform_id",
]


class Adapter:
    """Tiny wrapper: a name, a version, and a language-specific ``handle``.

    Adapters themselves live in submodules (
    ``minxg.contracts.runtime.<lang>``). This class only glues the
    string surface the rest of MINXG already understands.
    """

    __slots__ = ("name", "version", "status", "language", "callable")

    def __init__(self, name: str, version: str, status: str,
                 language: str, callable_) -> None:
        self.name = name
        self.version = version
        self.status = status
        self.language = language
        self.callable = callable_

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run the adapter against a payload, return its envelope dict.

        The stub adapters all return
        ``{"status": "stub", "language": ..., "name": ...}`` so callers
        can detect "not yet integrated" cleanly.
        """
        return self.callable(payload)

    def __repr__(self) -> str:
        return (
            f"Adapter({self.language}/{self.name} {self.version}, "
            f"status={self.status!r})"
        )


def list_adapters() -> List[Dict[str, str]]:
    """List every adapter as ``{name, version, status}`` dicts.

    Live adapters are loaded so the status reflects runtime availability
    (e.g. ``available`` vs ``disabled``) rather than the static manifest.
    Used by ``minxg polyglot-manifest``.
    """
    out: List[Dict[str, str]] = []
    for lang in POLYGLOT_LANGUAGES:
        info = POLYGLOT_MANIFEST[lang]
        adapter = load(lang)
        if adapter is not None:
            out.append({
                "name": adapter.name,
                "version": adapter.version,
                "status": adapter.status,
            })
        else:
            out.append({
                "name": info["name"],
                "version": info["version"],
                "status": info["status"],
            })
    return out


def load(language: str) -> Optional[Adapter]:
    """Return the live adapter object for ``language`` (case-insensitive).

    Falls back to ``None`` when the language is unknown.
    """
    from importlib import import_module

    lang = language.lower().strip()
    info = POLYGLOT_MANIFEST.get(lang)
    if not info:
        return None
    mod_name = info["module"]
    try:
        mod = import_module(mod_name)
    except Exception:
        return None
    return Adapter(
        name=getattr(mod, "ADAPTER_NAME", info["name"]),
        version=str(getattr(mod, "ADAPTER_VERSION", info["version"])),
        status=str(getattr(mod, "ADAPTER_STATUS", info["status"])),
        language=lang,
        callable_=getattr(mod, "invoke", getattr(mod, "handle", lambda _payload: {
            "status": "stub",
            "language": lang,
        })),
    )
