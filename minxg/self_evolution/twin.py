"""TwinEngine — runs a shadow copy of the live driver for candidate ops."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

from ..driver import DriverEngine, State, Operator


@dataclass
class TwinOutcome:
    accepted: bool
    baseline_drift: float
    candidate_drift: float
    step_deltas: Tuple[float, ...]
    summary: str


class TwinEngine:
    def __init__(self, n_steps: int = 16) -> None:
        self._n_steps = int(n_steps)

    def compare(
        self,
        live_engine: DriverEngine,
        candidate: Operator,
        target_idx: int,
        probe: State,
        *,
        tolerance: float = 0.0,
    ) -> TwinOutcome:
        baseline_drift = self._accumulate(self._run(live_engine, probe))
        twin = self._make_twin(live_engine, candidate, target_idx)
        cand_deltas = self._run(twin, probe)
        cand_drift = self._accumulate(cand_deltas)
        accepted = cand_drift <= baseline_drift + tolerance
        return TwinOutcome(
            accepted=accepted,
            baseline_drift=baseline_drift,
            candidate_drift=cand_drift,
            step_deltas=tuple(cand_deltas),
            summary="accept" if accepted else "reject",
        )

    def _make_twin(
        self,
        live: DriverEngine,
        candidate: Operator,
        target_idx: int,
    ) -> DriverEngine:
        clone_ops = list(live.operators())
        if 0 <= target_idx < len(clone_ops):
            clone_ops[target_idx] = candidate
        return DriverEngine(clone_ops, step_size=live.step_size())

    def _run(self, engine: DriverEngine, probe: State) -> List[float]:
        s = probe.clone()
        deltas: List[float] = []
        prev = dict(s.payload)
        for _ in range(self._n_steps):
            try:
                s, _ = engine.step(s)
            except Exception:
                deltas.append(float("inf"))
                break
            total = sum(
                (s.payload.get(k, 0.0) - prev.get(k, 0.0)) ** 2 for k in s.payload
            ) ** 0.5
            deltas.append(total)
            prev = dict(s.payload)
        return deltas

    @staticmethod
    def _accumulate(steps: List[float]) -> float:
        if any(d == float("inf") for d in steps):
            return float("inf")
        return sum(steps)
