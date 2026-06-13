"""minxg.driver.state — typed scalar bag with optional bounds, used
by the Temporal Operator-Field engine and the self_evolution twin.

minxg.cap.provides: state.bag, state.bounds
minxg.cap.requires: (none)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple


class StateError(ValueError):
    pass


@dataclass
class State:
    """Typed scalar-bag with conservative accessors."""
    payload: Dict[str, float] = field(default_factory=dict)
    bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    timestamp: float = 0.0

    def get(self, key: str, default: float = 0.0) -> float:
        return self.payload.get(key, default)

    def set(self, key: str, value: float) -> None:
        if key in self.bounds:
            lo, hi = self.bounds[key]
            if value < lo:
                value = lo
            elif value > hi:
                value = hi
        self.payload[key] = float(value)

    def add(self, key: str, delta: float) -> None:
        self.set(key, self.get(key) + delta)

    def keys(self) -> Iterable[str]:
        return self.payload.keys()

    def clone(self) -> "State":
        return State(
            payload=dict(self.payload),
            bounds=dict(self.bounds),
            timestamp=self.timestamp,
        )

    def distance(self, other: "State") -> float:
        if self.payload.keys() != other.payload.keys():
            shared = set(self.payload).intersection(other.payload)
        else:
            shared = set(self.payload)
        if not shared:
            return 0.0
        total = 0.0
        for k in shared:
            a = self.payload.get(k, 0.0)
            b = other.payload.get(k, 0.0)
            d = a - b
            total += d * d
        return total ** 0.5

    def merge(self, other: "State", *, prefix: str = "") -> None:
        for k, v in other.payload.items():
            self.set(f"{prefix}{k}", v)
