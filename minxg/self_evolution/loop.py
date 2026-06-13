"""EvolutionLoop — orchestrates the four components into a closed loop."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..driver import DriverEngine, State, Operator

from .failure_tour import FailureTour, Failure
from .field_forge import FieldForge, FieldProposal
from .twin import TwinEngine, TwinOutcome


@dataclass
class LoopConfig:
    probe_state: State
    n_steps: int = 16
    tolerance: float = 0.05
    max_replaces_per_cycle: int = 3


@dataclass
class CycleRecord:
    applied: List[FieldProposal]
    rejected: List[FieldProposal]
    failures_seen: int


class EvolutionLoop:
    def __init__(
        self,
        live_engine: DriverEngine,
        tour: FailureTour,
        forge: FieldForge,
        twin: TwinEngine,
    ) -> None:
        self._engine = live_engine
        self._tour = tour
        self._forge = forge
        self._twin = twin

    def cycle(self, config: LoopConfig) -> CycleRecord:
        engine = self._engine
        tour = self._tour
        failures = tour.recent()
        if not failures:
            return CycleRecord(applied=[], rejected=[], failures_seen=0)

        by_op = tour.by_op()
        proposals = self._forge.propose(by_op, config.probe_state)

        applied: List[FieldProposal] = []
        rejected: List[FieldProposal] = []
        for proposal in proposals:
            if len(applied) >= config.max_replaces_per_cycle:
                rejected.append(proposal)
                continue
            target_idx = self._match_index(engine, proposal.replace_op)
            if target_idx is None:
                rejected.append(proposal)
                continue
            candidate = self._candidate_operator(proposal.candidate_id)
            if candidate is None:
                rejected.append(proposal)
                continue
            outcome = self._twin.compare(
                engine,
                candidate,
                target_idx,
                config.probe_state,
                tolerance=config.tolerance,
            )
            if outcome.accepted:
                engine.replace_operator(target_idx, candidate)
                applied.append(proposal)
            else:
                rejected.append(proposal)
        return CycleRecord(applied=applied, rejected=rejected, failures_seen=len(failures))

    def _match_index(self, engine: DriverEngine, name: str) -> Optional[int]:
        for i, op in enumerate(engine.operators()):
            if op.name == name:
                return i
        return None

    def _candidate_operator(self, cell_id: str) -> Optional[Operator]:
        try:
            cell = self._forge._registry.get(cell_id)
        except Exception:
            return None
        fn = getattr(cell, "apply", None) or getattr(cell, "__call__", None)
        if fn is None:
            return None

        class _Adapter(Operator):
            def __init__(self_inner, n, f):
                self_inner._f = f

            def apply(self_inner, state: State) -> State:
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

        adapter = _Adapter(cell_id, fn)
        setattr(adapter, "name", cell_id)
        return adapter
