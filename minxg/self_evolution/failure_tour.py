"""FailureTour — records failures observed by the driver engine.

The driver never raises on drift alone; subdivision handles that. This
tour captures the *unrecoverable* failures: states with NaN, divergent
amplitudes, repeated-step stalls. Each Failure is enough metadata for
the FieldForge to propose a replacement operator without inspecting
private engine state.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Failure:
    step: int
    state_signature: Tuple[Tuple[str, float], ...]
    diagnostics: Dict[str, float]
    caused_by: Optional[str] = None
    note: str = ""


class FailureTour:
    def __init__(self, max_history: int = 1000) -> None:
        self._log: List[Failure] = []
        self._max = int(max_history)
        self._last_step: int = -1

    def record(
        self,
        step: int,
        state_payload: Dict[str, float],
        diagnostics: Dict[str, float],
        caused_by: Optional[str] = None,
        note: str = "",
    ) -> Failure:
        sig = tuple(sorted(state_payload.items()))
        failure = Failure(
            step=step,
            state_signature=sig,
            diagnostics=dict(diagnostics),
            caused_by=caused_by,
            note=note,
        )
        self._log.append(failure)
        if len(self._log) > self._max:
            self._log = self._log[-self._max:]
        self._last_step = step
        return failure

    def detect_from_state(
        self,
        step: int,
        payload: Dict[str, float],
        caused_by: Optional[str] = None,
    ) -> Optional[Failure]:
        nan_keys = [k for k, v in payload.items() if not math.isfinite(v)]
        huge = any(abs(v) > 1e9 for v in payload.values())
        if not (nan_keys or huge):
            return None
        return self.record(
            step=step,
            state_payload=payload,
            diagnostics={
                "nan_keys": len(nan_keys),
                "amplitude": max((abs(v) for v in payload.values()), default=0.0),
            },
            caused_by=caused_by,
            note="non-finite or unbounded amplitude" if huge else "non-finite state",
        )

    def by_op(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for f in self._log:
            if f.caused_by:
                out[f.caused_by] = out.get(f.caused_by, 0) + 1
        return out

    def recent(self, limit: int = 20) -> List[Failure]:
        return list(self._log[-limit:])

    def __len__(self) -> int:
        return len(self._log)
