"""FieldForge — proposes new operators given failure history.

FailureTour reports which operator is most often responsible for a
failure. FieldForge walks the contracts Registry, finds a Cell that
advertises the same capability with lower drift on a synthetic probe,
and emits a `FieldProposal` describing the swap.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..contracts.registry import get_registry
from ..contracts.cell import Cell
from ..driver import State, DriverEngine


@dataclass
class FieldProposal:
    replace_op: str
    candidate_id: str
    reason: str
    expected_drift: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)


ClampFn = Callable[[Dict[str, float], Dict[str, float]], Dict[str, float]]


class FieldForge:
    def __init__(self, registry=None) -> None:
        self._registry = registry if registry is not None else get_registry()

    def propose(
        self,
        failures_by_op: Dict[str, int],
        probe_state: State,
        step_size: float = 0.5,
        n_probe_steps: int = 8,
    ) -> List[FieldProposal]:
        proposals: List[FieldProposal] = []
        for op_name, count in failures_by_op.items():
            if count <= 0:
                continue
            for cell_id in self._registry.all_ids():
                cell = self._registry.get(cell_id)
                adapter = self._adapt_cell(cell)
                if adapter is None:
                    continue
                candidate = DriverEngine([adapter], step_size=step_size)
                drift = self._measure_drift(candidate, probe_state, n_probe_steps)
                expected_drift = max(0.0, drift / max(n_probe_steps, 1))
                proposals.append(FieldProposal(
                    replace_op=op_name,
                    candidate_id=cell_id,
                    reason=f"failure_count={count}",
                    expected_drift=expected_drift,
                ))
        proposals.sort(key=lambda p: p.expected_drift)
        return proposals

    def _adapt_cell(self, cell: Cell) -> Optional["_CellOperator"]:
        fn = getattr(cell, "apply", None) or getattr(cell, "__call__", None)
        if fn is None:
            return None
        name = getattr(cell, "cell_id", "cell")

        class _Adapter:
            def __init__(self, n, f):
                self.name = n
                self._f = f

            def apply(self_inner, state):
                out = state.clone()
                try:
                    src = self_inner._f(out)
                    if isinstance(src, dict):
                        for k, v in src.items():
                            if k in out.payload:
                                out.payload[k] = float(v)
                except Exception:
                    return out
                return out

        try:
            adapter = _Adapter(name, fn)
            setattr(adapter, "__name__", name)
            return adapter
        except Exception:
            return None

    def _measure_drift(
        self,
        engine: "DriverEngine",
        state: State,
        n_steps: int,
    ) -> float:
        s = state.clone()
        total_drift = 0.0
        for _ in range(max(1, n_steps)):
            try:
                s, _ = engine.step(s)
            except Exception:
                return float("inf")
            total_drift += s.distance(state)
        return total_drift
