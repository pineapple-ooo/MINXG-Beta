"""Lifecycle — explicit phase markers for Cells and Registries.

A Cell passes through five phases. Other components observe phase
transitions instead of needing to know the Cell's internals.

    BORN     → just imported, not registered
    MUTABLE  → registered, accept further changes
    LIVE     → registry locked, Cell is read-only
    QUIET    → Cold-storage: still discoverable, but excluded from routing
    GONE     → Fully retired; metadata purged
""""
from __future__ import annotations
from enum import Enum
from typing import Callable, List


class LifecyclePhase(str, Enum):
    BORN = "born"
    MUTABLE = "mutable"
    LIVE = "live"
    QUIET = "quiet"
    GONE = "gone"


class Lifecycle:
    def __init__(self, initial: LifecyclePhase = LifecyclePhase.BORN) -> None:
        self._phase = initial
        self._hooks: List[Callable[[LifecyclePhase, LifecyclePhase], None]] = []

    @property
    def phase(self) -> LifecyclePhase:
        return self._phase

    def transition(self, target: LifecyclePhase) -> None:
        if target == self._phase:
            return
        previous = self._phase
        self._phase = target
        for hook in list(self._hooks):
            hook(previous, target)

    def on_transition(self, hook: Callable[[LifecyclePhase, LifecyclePhase], None]) -> None:
        self._hooks.append(hook)
