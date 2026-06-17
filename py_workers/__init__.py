"""Backward-compat alias: py_workers → minxg.

The package was renamed from py_workers to minxg in v0.0.2.
This stub keeps `import py_workers` and `from py_workers.<x>` working by
forwarding every attribute/sub-module lookup to the corresponding minxg
attribute or, for sub-modules, exposing them at the matching py_workers
path so legacy imports keep functioning.

Sub-module mapping for the Five-Pillar layout (v1.1.0+):
    py_workers.base               → minxg.base
    py_workers.server             → minxg.server
    py_workers.operators          → minxg.operators
    py_workers.<short>            → minxg.five_pillars.<pillar>.<short>
    py_workers.five_pillars.<...> → minxg.five_pillars.<...>
    py_workers.<math_pillar>      → minxg.<math_pillar>
"""
import sys
import importlib
import minxg as _minxg

sys.modules["py_workers"] = _minxg

_MINXG_PREFIX = f"{_minxg.__name__}."
_PILLAR_MODULE_SET = {
    "scalar": "five_pillars.scalar",
    "aggregate": "five_pillars.aggregate",
    "io": "five_pillars.io",
    "dispatch": "five_pillars.dispatch",
    "transform": "five_pillars.transform",
}
_MATH_PILLARS = ("ga", "cat", "infogeo", "topo", "chaos", "fiber")

__all__ = getattr(_minxg, "__all__", ())
VERSION = getattr(_minxg, "VERSION", "1.1.0")


def __getattr__(name):
    target = f"{_MINXG_PREFIX}{name}"
    if name in _PILLAR_MODULE_SET:
        full = f"{_MINXG_PREFIX}{_PILLAR_MODULE_SET[name]}"
        return importlib.import_module(full)
    if name in _MATH_PILLARS:
        return importlib.import_module(target)
    if hasattr(_minxg, "five_pillars"):
        fp = _minxg.five_pillars
        for pillar in _PILLAR_MODULE_SET.values():
            full = f"five_pillars.{pillar.split('.', 1)[1]}.{name}" if "." in pillar else f"five_pillars.{name}"
            try:
                mod = importlib.import_module(f"{_MINXG_PREFIX}{full}")
                sys.modules[f"py_workers.{name}"] = mod
                return mod
            except ImportError:
                continue
    if hasattr(_minxg, name):
        return getattr(_minxg, name)
    raise AttributeError(f"module 'py_workers' has no attribute {name!r}")
