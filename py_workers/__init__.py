"""Backward-compat alias: py_workers -> minxg.

The package was renamed from py_workers to minxg in v0.0.2. This stub
keeps `import py_workers` and `from py_workers.<x>` working by exposing
the same surface but routing every attribute lookup through minxg so
nothing forks.

The trick used here: py_workers is registered in sys.modules as its OWN
module (not minxg), with its OWN __getattr__. py_workers.X therefore
goes through this file's getattr, not minxg's. That way the legacy
short pillar names (scalar, io, dispatch, aggregate, transform) and the
math pillars (ga, cat, ...) all resolve correctly here, in addition to
the canonical minxg paths.
"""
from __future__ import annotations

import importlib
import sys

import minxg as _minxg


__all__ = getattr(_minxg, "__all__", ())
VERSION = getattr(_minxg, "VERSION", "0.11.0")

PILLAR_MODULE_SET = {
    "scalar": "five_pillars.scalar",
    "aggregate": "five_pillars.aggregate",
    "io": "five_pillars.io",
    "dispatch": "five_pillars.dispatch",
    "transform": "five_pillars.transform",
}
MATH_PILLAR_NAMES = ("ga", "cat", "infogeo", "topo", "chaos", "fiber")
PILLAR_KEYS = set(PILLAR_MODULE_SET.keys())


def __getattr__(name: str):
    # py_workers.<pillar> -> minxg.five_pillars.<pillar>
    if name in PILLAR_MODULE_SET:
        mod = importlib.import_module(f"minxg.{PILLAR_MODULE_SET[name]}")
        sys.modules[f"py_workers.{name}"] = mod
        return mod
    # py_workers.<math> -> minxg.<math>
    if name in MATH_PILLAR_NAMES:
        mod = importlib.import_module(f"minxg.{name}")
        sys.modules[f"py_workers.{name}"] = mod
        return mod
    # py_workers.five_pillars -> minxg.five_pillars
    if name == "five_pillars":
        return importlib.import_module("minxg.five_pillars")
    # Anything else: delegate to minxg.
    if hasattr(_minxg, name):
        return getattr(_minxg, name)
    raise AttributeError(f"module 'py_workers' has no attribute {name!r}")


def __dir__():
    base = set(getattr(_minxg, "__all__", ()))
    base.update(PILLAR_KEYS)
    base.update(MATH_PILLAR_NAMES)
    base.update({"five_pillars", "VERSION", "cap", "operators"})
    return sorted(base)
