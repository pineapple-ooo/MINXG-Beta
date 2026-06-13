"""Engine — explicit-Euler driver with adaptive sub-stepping.

The engine integrates a stack of Operators across a State. Each step:

  1. Snapshot the State.
  2. For every Operator in execution tier, compute its delta.
  3. Apply the delta scaled by `dt`.
  4. Drift-check: if the per-step displacement exceeds `max_drift`,
     subdivide `dt` up to `max_subdivisions` times.

Steps are recorded as StepReports; an EnginePhase observable lets
external code observe transitions without coupling to the engine.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .operator import Operator, Identity
from .state import State


class EnginePhase(str, Enum):
    READY = "ready"
    STEPPING = "stepping"
    PAUSED = "paused"
    HALTED = "halted"
    FAULTED = "faulted"


@dataclass
class StepReport:
    step: int
    timestamp: float
    drift: float
    subdivisions: int
    operator_count: int
    notes: List[str] = field(default_factory=list)


class DriverEngine:
    def __init__(
        self,
        operators: Optional[List[Operator]] = None,
        *,
        step_size: float = 1.0,
        max_drift: float = 1.0,
        max_subdivisions: int = 6,
    ) -> None:
        self._operators: List[Operator] = list(operators or [])
        self._dt = float(step_size)
        self._max_drift = float(max_drift)
        self._max_subdiv = max(1, int(max_subdivisions))
        self._phase = EnginePhase.READY
        self._listeners: List[Callable[[EnginePhase, EnginePhase], None]] = []
        self._log: List[StepReport] = []
        self._step_count = 0

    @property
    def phase(self) -> EnginePhase:
        return self._phase

    @property
    def log(self) -> List[StepReport]:
        return list(self._log)

    def add_operator(self, op: Operator) -> None:
        self._operators.append(op)

    def replace_operator(self, idx: int, op: Operator) -> None:
        self._operators[idx] = op

    def operators(self) -> Tuple[Operator, ...]:
        return tuple(self._operators)

    def step_size(self) -> float:
        return self._dt

    def max_subdivisions(self) -> int:
        return self._max_subdiv

    def remove_operator(self, name: str) -> bool:
        before = len(self._operators)
        self._operators = [o for o in self._operators if o.name != name]
        return len(self._operators) != before

    def on_phase(self, hook: Callable[[EnginePhase, EnginePhase], None]) -> None:
        self._listeners.append(hook)

    def _set_phase(self, target: EnginePhase) -> None:
        if target == self._phase:
            return
        previous, self._phase = self._phase, target
        for hook in list(self._listeners):
            hook(previous, target)

    def step(self, state: State) -> Tuple[State, StepReport]:
        if self._phase in (EnginePhase.HALTED, EnginePhase.FAULTED):
            raise RuntimeError(f"engine is {self._phase}; reset() to continue")
        self._set_phase(EnginePhase.STEPPING)

        subdivisions = 0
        notes: List[str] = []
        dt = self._dt
        working = state.clone()
        last_drift = 0.0

        while subdivisions <= self._max_subdiv:
            probe = working.clone()
            delta_state = self._compose(probe, dt)
            drift = working.distance(delta_state)
            last_drift = drift
            if drift <= self._max_drift or subdivisions >= self._max_subdiv:
                working = delta_state
                break
            dt *= 0.5
            subdivisions += 1
            notes.append(f"subdivide dt={dt:.6f} drift={drift:.4f}")

        working.timestamp = state.timestamp + self._dt

        report = StepReport(
            step=self._step_count,
            timestamp=working.timestamp,
            drift=last_drift,
            subdivisions=subdivisions,
            operator_count=len(self._operators),
            notes=notes,
        )
        self._step_count += 1
        self._log.append(report)
        self._set_phase(EnginePhase.READY)
        return working, report

    def run(self, state: State, n_steps: int) -> Tuple[State, List[StepReport]]:
        out = state
        reports: List[StepReport] = []
        for _ in range(n_steps):
            out, report = self.step(out)
            reports.append(report)
        return out, reports

    def reset(self) -> None:
        self._log.clear()
        self._step_count = 0
        self._phase = EnginePhase.READY

    def pause(self) -> None:
        if self._phase == EnginePhase.STEPPING:
            return
        self._set_phase(EnginePhase.PAUSED)

    def halt(self) -> None:
        self._set_phase(EnginePhase.HALTED)

    def _compose(self, state: State, dt: float) -> State:
        result = state.clone()
        for op in self._operators:
            next_state = op.apply(result.clone())
            scale = dt / self._dt
            for key in result.payload:
                delta = next_state.payload.get(key, 0.0) - result.payload[key]
                result.payload[key] = result.payload[key] + delta * scale
        return result
