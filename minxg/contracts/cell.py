"""Cell — the smallest pluggable capability unit in MINXG.

A Cell declares itself a `Cell` by exposing the three attributes:
    cell_id : str   — unique dotted identifier, e.g. "fs.read"
    cell_version : str
    cell_capabilities : tuple[str, ...]   — what this Cell can do

The `cell` decorator (and `CellMeta`) auto-discover tool methods (those
decorated with `@tool`) and fold their declared category into capabilities.
Cells may also be standalone plain objects — only `cell_id` is required to
be discoverable through the Registry.
""""
from __future__ import annotations
from typing import Any, Callable, Iterable, Protocol, runtime_checkable


@runtime_checkable
class Cell(Protocol):
    cell_id: str
    cell_version: str

    @property
    def cell_capabilities(self) -> tuple[str, ...]: ...


class CellMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        cap_set: set[str] = set()
        for base in bases:
            cap_set.update(getattr(base, "cell_capabilities", ()) or ())
        for value in namespace.values():
            cat = getattr(value, "_tool_category", None)
            if cat:
                cap_set.add(cat)
            op_id = getattr(value, "_op_id", None)
            if op_id is not None:
                cap_set.add(f"op:{op_id}")
        if "cell_capabilities" not in namespace:
            cls.cell_capabilities = tuple(sorted(cap_set))
        if "cell_version" not in namespace:
            cls.cell_version = "0.0.0"
        if "cell_id" not in namespace:
            cls.cell_id = ""
        return cls


def capability(name: str) -> Callable[[Callable], Callable]:
    def deco(fn: Callable) -> Callable:
        fn._cell_capability = name
        return fn
    return deco


def requires(*capability_names: str) -> Callable[[type], type]:
    def deco(cls: type) -> type:
        existing = list(getattr(cls, "_cell_requires", ()))
        existing.extend(capability_names)
        cls._cell_requires = tuple(existing)
        return cls
    return deco
