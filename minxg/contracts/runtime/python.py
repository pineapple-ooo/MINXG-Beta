"""Adapter: native Python ecosystem.

This is the only "always-active" adapter — every other language can
fall back to it when its own runtime is unavailable.
"""
from __future__ import annotations

ADAPTER_NAME = "python"
ADAPTER_VERSION = "0.17.1"
ADAPTER_STATUS = "native"


def handle(payload):  # type: ignore[no-untyped-def]
    """Pass-through handler — Python is the default dispatch."""
    return {
        "status": "ok",
        "language": "python",
        "echo": payload,
    }


def invoke(payload):  # type: ignore[no-untyped-def]
    """Alias for ``handle`` used by the live adapter registry."""
    return handle(payload)


__all__ = ["ADAPTER_NAME", "ADAPTER_VERSION", "ADAPTER_STATUS", "handle", "invoke"]
