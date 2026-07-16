"""minxg/tiers/devtools/__init__.py — Tier-aware developer tools.

This sub-module provides tier classification for every worker
in the current registry and exposes a ``classify`` helper that
the CLI / gateway can use for tool discovery.

All workers added in v0.18.0 (dev_forge, apkstudio, etc.)
carry an explicit ``.tier`` attribute so the classification
is declarative.
"""

from __future__ import annotations

from minxg.tiers import AI_TIER, USER_TIER, CODE_TIER, TierRegistry, classify

__all__ = [
    "AI_TIER", "USER_TIER", "CODE_TIER",
    "TierRegistry", "classify",
]