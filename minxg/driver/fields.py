"""Fields — pre-built Operator generators for common dynamics.

A Field is an Operator factory: given a configuration it returns an
Operator ready to drop into a DriverEngine. Configurations are plain
dicts so swapping a Field never breaks the engine signature.
"""
from __future__ import annotations
import math
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from .operator import Operator
from .state import State


class Field:
    def build(self, **kwargs: Any) -> Operator:
        raise NotImplementedError


def arithmetic_field(formula: Callable[[Dict[str, float]], Dict[str, float]], *, name: str = "arithmetic") -> Operator:
    """Pure-arithmetic lambdas. `formula(state_dict) → delta_dict`."""
    class _A(Operator):
        def apply(self, state: State) -> State:
            out = state.clone()
            delta = formula(dict(out.payload))
            for k, v in delta.items():
                if k in out.payload:
                    out.payload[k] += float(v)
                else:
                    out.payload[k] = float(v)
            return out
    _A.name = name
    return _A()


def parametric_field(name: str, gain: float, axis: str) -> Operator:
    """Linearly scales one axis by gain."""
    class _P(Operator):
        def apply(self, state: State) -> State:
            out = state.clone()
            if axis in out.payload:
                out.payload[axis] += gain
            return out
    _P.name = name
    return _P()


def clamp_field(lo: float, hi: float) -> Operator:
    """Clamps every state component into [lo, hi]."""
    class _C(Operator):
        name = "clamp"

        def apply(self, state: State) -> State:
            out = state.clone()
            for k, v in list(out.payload.items()):
                if v < lo:
                    out.payload[k] = lo
                elif v > hi:
                    out.payload[k] = hi
            return out
    return _C()


def smoothing_field(rate: float = 0.5) -> Operator:
    """Exponential decay toward zero at the given rate. Stabilises fields."""
    if not 0.0 <= rate <= 1.0:
        raise ValueError("smoothing rate must be in [0, 1]")

    class _S(Operator):
        def __init__(self) -> None:
            super().__init__()
            self.name = "smooth"

        def apply(self, state: State) -> State:
            out = state.clone()
            factor = 1.0 - rate
            for k, v in list(out.payload.items()):
                out.payload[k] = v * factor
            return out
    return _S()
