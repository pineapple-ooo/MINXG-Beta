"""minxg.driver — Temporal Operator-Field driver engine.

This is MINXG's self-developed driver architecture. Unlike standard task
graphs that simply invoke callables in order, the driver treats each
operator as a *vector field* on a shared state manifold and advances the
state through explicit Euler integration.

Why this design?

* Order independence emerges from the field composition: swapping two
  commutative operators never changes the result, so individual operators
  can be edited, replaced, or removed without disturbing siblings.
* Operators are pure functions on a `State` object; they cannot reach
  out of the field. This is the property that makes "change one module
  without touching the rest" a structural guarantee, not a convention.
* Drift control: every step computes a divergence estimate; large drift
  triggers automatic sub-stepping. The driver stays stable for chaotic
  fields too.

Three components:

    State        — typed payload (`dict[str, float]`) with bounds/clamps
    Operator     — pure mapping State → State, possibly parameterised
    DriverEngine — integration loop, schedules Operators by tier
"""
from .state import State, StateError
from .operator import Operator, Identity, Composition
from .engine import DriverEngine, StepReport, EnginePhase
from .fields import Field, arithmetic_field, parametric_field, clamp_field, smoothing_field

__all__ = [
    "State", "StateError",
    "Operator", "Identity", "Composition",
    "DriverEngine", "StepReport", "EnginePhase",
    "Field", "arithmetic_field", "parametric_field",
    "clamp_field", "smoothing_field",
]
