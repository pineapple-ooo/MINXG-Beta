"""Registry — type-keyed catalogue of Cells and Ports.

The Registry is the only shared object across Cells. It is created once,
populated through `cell.register(...)`, then `lock()`-ed. After locking
the catalogue is frozen; modifying a single Cell never invalidates other
Cells because nothing inside the catalogue points back at them.
""""
from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Type
from .cell import Cell
from .lifecycle import LifecyclePhase


class Registry:
    def __init__(self) -> None:
        self._cells: Dict[str, Cell] = {}
        self._by_capability: Dict[str, list[str]] = {}
        self._versions: Dict[str, str] = {}
        self._locked = False
        self.lifecycle = LifecyclePhase.BORN

    def register(self, instance_or_class: Any, *, replaces: Optional[str] = None) -> str:
        if self._locked:
            raise RuntimeError("registry is locked; unlock() before further register()")
        cell_id = getattr(instance_or_class, "cell_id", None) or \
            f"{instance_or_class.__module__}.{instance_or_class.__name__}"
        if not replaces:
            if cell_id in self._cells:
                raise ValueError(f"cell {cell_id!r} already registered")
        else:
            cell_id = replaces
            self._cells.pop(cell_id, None)
        instance = instance_or_class() if isinstance(instance_or_class, type) else instance_or_class
        self._cells[cell_id] = instance
        self._versions[cell_id] = getattr(instance, "cell_version", "0.0.0")
        for cap in getattr(instance, "cell_capabilities", ()) or ():
            self._by_capability.setdefault(cap, []).append(cell_id)
        return cell_id

    def get(self, cell_id: str) -> Cell:
        if cell_id not in self._cells:
            raise KeyError(cell_id)
        return self._cells[cell_id]

    def has(self, cell_id: str) -> bool:
        return cell_id in self._cells

    def find_by_capability(self, capability: str) -> list[Cell]:
        return [self._cells[cid] for cid in self._by_capability.get(capability, ())]

    def capabilities_of(self, cell_id: str) -> tuple[str, ...]:
        cell = self.get(cell_id)
        return tuple(getattr(cell, "cell_capabilities", ()) or ())

    def all_ids(self) -> tuple[str, ...]:
        return tuple(self._cells)

    def lock(self) -> None:
        self._locked = True
        self.lifecycle = LifecyclePhase.LIVE

    def unlock(self) -> None:
        self._locked = False
        self.lifecycle = LifecyclePhase.MUTABLE

    @property
    def locked(self) -> bool:
        return self._locked

    def __len__(self) -> int:
        return len(self._cells)

    def __contains__(self, cell_id: object) -> bool:
        return isinstance(cell_id, str) and cell_id in self._cells


_DEFAULT: Optional[Registry] = None


def get_registry() -> Registry:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Registry()
    return _DEFAULT


def reset_registry() -> Registry:
    global _DEFAULT
    _DEFAULT = Registry()
    return _DEFAULT


def cell(instance_or_class: Any, *, replaces: Optional[str] = None) -> Any:
    """Decorator + runtime helper. Register a Cell on the default Registry.

    Editing the decorated class does NOT affect any other registered Cell,
    and re-importing the module does NOT force re-registration of siblings.
    """"
    return get_registry().register(instance_or_class, replaces=replaces)
