"""Operator — pure mappings on the State manifold.

Two operators are equal iff they produce equal State deltas for every
input. This equality is the key reason individual Operators can be
replaced or re-ordered: composition is associative, identity exists,
and the module boundary is small enough to hold in your head.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from .state import State


class Operator:
    name: str = "operator"

    def apply(self, state: State) -> State:
        return state

    def __call__(self, state: State) -> State:
        return self.apply(state)

    def magnitude(self, state: State) -> float:
        before = state.clone()
        after = self.apply(before.clone())
        return state.distance(after)


class Identity(Operator):
    name = "identity"

    def apply(self, state: State) -> State:
        return state.clone()


@dataclass
class Composition(Operator):
    """Build an Operator by composing two existing Operators in order."""
    left: Operator
    right: Operator
    name: str = field(default="composition")

    def apply(self, state: State) -> State:
        return self.right.apply(self.left.apply(state))


class LambdaOperator(Operator):
    """Functional adapter. Wraps a pure mapping state → delta dict into
    an Operator without exposing the engine's internals.
    """
    def __init__(self, name: str, fn: Callable[[State], Dict[str, float]]) -> None:
        self.name = name
        self._fn = fn

    def apply(self, state: State) -> State:
        clone = state.clone()
        for k, v in self._fn(clone).items():
            clone.add(k, v)
        return clone
