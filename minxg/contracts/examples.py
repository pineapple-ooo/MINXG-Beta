"""Demonstration Cell shipped with contracts/.

Use as a copy-paste template: register your own cells with the same
shape, drop them next to this file, and they auto-appear in the
Registry without touching any other module.
"""
from __future__ import annotations
from typing import Any, Dict
from .cell import CellMeta


class GreetingCell(metaclass=CellMeta):
    cell_id = "demo.greeting"
    cell_version = "0.16.0"

    def greet(self, name: str = "world") -> Dict[str, Any]:
        return {"greeting": f"hello, {name}"}

    def farewell(self, name: str = "world") -> Dict[str, Any]:
        return {"farewell": f"goodbye, {name}"}
