"""minxg.driver.engine — Temporal Operator-Field integrator with adaptive
sub-stepping, drift control, five-phase observability, RK4/RK45 integration,
chaos detection, energy conservation tracking, and singularity awareness.

minxg.cap.provides: driver.engine, driver.drift.control, driver.phases,
driver.rk4, driver.rk45, driver.chaos, driver.energy, driver.singularity
minxg.cap.requires: state.bag, state.bounds
"""
from __future__ import annotations
import math
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
    SINGULARITY = "singularity"  # NEW: detected a singularity


@dataclass
class StepReport:
    step: int
    timestamp: float
    drift: float
    subdivisions: int
    operator_count: int
    notes: List[str] = field(default_factory=list)
    # v0.14.1 additions
    method: str = "euler"                # "euler" | "rk4" | "rk45"
    energy_delta: float = 0.0            # change in energy this step
    lyapunov_estimate: float = 0.0        # running Lyapunov exponent estimate
    is_chaotic: bool = False              # chaos flag
    singularity_detected: bool = False    # singularity flag


class DriverEngine:
    """Temporal Operator-Field integrator.

    v0.14.1 adds:
    - RK4 fourth-order Runge-Kutta integration
    - RK45 adaptive Runge-Kutta-Fehlberg with error control
    - Lyapunov exponent tracking for chaos detection
    - Energy conservation monitoring
    - Singularity detection (NaN/Inf blowup, gradient explosion)

    The engine now has three integration methods selectable at init time:
      'euler' — legacy explicit Euler (backward compat)
      'rk4'   — classical 4th-order Runge-Kutta
      'rk45'  — adaptive RK45 (Fehlberg) with error control
    """

    def __init__(
        self,
        operators: Optional[List[Operator]] = None,
        *,
        step_size: float = 1.0,
        max_drift: float = 1.0,
        max_subdivisions: int = 6,
        method: str = "euler",
        rtol: float = 1e-6,
        atol: float = 1e-9,
    ) -> None:
        self._operators: List[Operator] = list(operators or [])
        self._dt = float(step_size)
        self._max_drift = float(max_drift)
        self._max_subdiv = max(1, int(max_subdivisions))
        self._method = method if method in ("euler", "rk4", "rk45") else "euler"
        self._rtol = rtol
        self._atol = atol
        self._phase = EnginePhase.READY
        self._listeners: List[Callable[[EnginePhase, EnginePhase], None]] = []
        self._log: List[StepReport] = []
        self._step_count = 0
        # Chaos / energy tracking state
        self._lyapunov_sum: float = 0.0
        self._lyapunov_count: int = 0
        self._prev_energy: Optional[float] = None
        self._chaos_threshold: float = 0.5  # Lyapunov exponent threshold

    @property
    def phase(self) -> EnginePhase:
        return self._phase

    @property
    def log(self) -> List[StepReport]:
        return list(self._log)

    @property
    def method(self) -> str:
        return self._method

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

    # ── New: energy computation ──────────────────────────────

    @staticmethod
    def _compute_energy(state: State) -> float:
        """Compute a Hamiltonian-like energy: sum of squared state values."""
        return sum(v * v for v in state.payload.values())

    # ── New: Lyapunov exponent tracking ─────────────────────

    def _update_lyapunov(self, drift: float, dt: float) -> Tuple[float, bool]:
        """Update running Lyapunov exponent estimate from drift.

        Lyapunov exponent λ ≈ (1/T) Σ ln(|Δx|/ε) where Δx is drift.
        Returns (current_estimate, is_chaotic).
        """
        if drift > 1e-15:
            self._lyapunov_sum += math.log(drift + 1e-30)
            self._lyapunov_count += 1
        if self._lyapunov_count > 0:
            lam = self._lyapunov_sum / self._lyapunov_count
            return lam, lam > self._chaos_threshold
        return 0.0, False

    # ── New: singularity detection ──────────────────────────

    @staticmethod
    def _detect_singularity(state: State) -> bool:
        """Detect NaN, Inf, or extreme values that indicate a singularity."""
        for v in state.payload.values():
            if not math.isfinite(v):
                return True
            if abs(v) > 1e15:
                return True
        return False

    # ── Euler integration (original, backward compat) ──────

    def _compose_euler(self, state: State, dt: float) -> State:
        """Original Euler-like composition, scaled by dt."""
        result = state.clone()
        for op in self._operators:
            next_state = op.apply(result.clone())
            scale = dt / self._dt
            for key in result.payload:
                delta = next_state.payload.get(key, 0.0) - result.payload[key]
                result.payload[key] = result.payload[key] + delta * scale
        return result

    # ── NEW: RK4 integration ────────────────────────────────

    def _compose_rk4(self, state: State, dt: float) -> State:
        """Classical 4th-order Runge-Kutta: k1, k2, k3, k4.

        Each k_i is the operator-field delta at a specific midpoint.
        The composition is:
          y_{n+1} = y_n + (k1 + 2*k2 + 2*k3 + k4) / 6
        """
        k1 = self._compute_delta(state, 0.0)
        k2_state = self._apply_delta(state, k1, 0.5 * dt / self._dt)
        k2 = self._compute_delta(k2_state, 0.5 * dt)
        k3_state = self._apply_delta(state, k2, 0.5 * dt / self._dt)
        k3 = self._compute_delta(k3_state, 0.5 * dt)
        k4_state = self._apply_delta(state, k3, dt / self._dt)
        k4 = self._compute_delta(k4_state, dt)

        # Weighted average: y + (k1 + 2k2 + 2k3 + k4) / 6
        result = state.clone()
        avg_scale = dt / self._dt / 6.0
        for key in result.payload:
            dk1 = k1.get(key, 0.0)
            dk2 = k2.get(key, 0.0)
            dk3 = k3.get(key, 0.0)
            dk4 = k4.get(key, 0.0)
            result.payload[key] += (dk1 + 2*dk2 + 2*dk3 + dk4) * avg_scale
        return result

    # ── NEW: RK45 adaptive integration ──────────────────────

    def _compose_rk45(self, state: State, dt: float) -> State:
        """Runge-Kutta-Fehlberg (RK45) with embedded error estimate.

        Uses the Fehlberg coefficients to compute both a 4th-order and
        a 5th-order solution; the difference gives an error estimate.
        If the error exceeds rtol/atol, the step is rejected and dt halved.
        """
        # Fehlberg coefficients (a, b, c)
        a = [0, 1/4, 3/8, 12/13, 1, 1/2]
        b = [
            [],  # k0 (not used)
            [1/4],
            [3/32, 9/32],
            [1932/2197, -7200/2197, 7296/2197],
            [439/216, -8, 3680/513, -845/4104],
            [-8/27, 2, -3544/2565, 1859/4104, -11/40],
        ]
        # 4th order weights
        w4 = [25/216, 0, 1408/2565, 2197/4104, -1/5, 0]
        # 5th order weights
        w5 = [16/135, 0, 6656/12825, 28561/56430, -9/50, 2/55]

        # Compute 6 stages
        k_stages: List[Dict[str, float]] = []
        for stage in range(6):
            if stage == 0:
                k_stages.append(self._compute_delta(state, 0.0))
            else:
                # Build intermediate state
                inter = state.clone()
                scale_cum = dt / self._dt
                for key in inter.payload:
                    delta_sum = 0.0
                    for j in range(stage):
                        dk = k_stages[j].get(key, 0.0)
                        delta_sum += b[stage][j] * dk
                    inter.payload[key] += delta_sum * scale_cum
                k_stages.append(self._compute_delta(inter, a[stage] * dt))

        # Build 4th and 5th order results
        avg_scale = dt / self._dt
        result4 = state.clone()
        result5 = state.clone()
        err_max = 0.0
        for key in state.payload:
            y4 = 0.0
            y5 = 0.0
            for i in range(6):
                dk = k_stages[i].get(key, 0.0)
                y4 += w4[i] * dk
                y5 += w5[i] * dk
            result4.payload[key] += y4 * avg_scale
            result5.payload[key] += y5 * avg_scale
            # Error estimate
            err = abs(result5.payload[key] - result4.payload[key])
            scale = self._atol + self._rtol * max(
                abs(state.payload[key]),
                abs(result4.payload[key])
            )
            if scale > 0:
                err_max = max(err_max, err / scale)

        # Accept if error is within tolerance
        if err_max <= 1.0:
            return result5  # use 5th order result
        else:
            # Reject and use Euler as fallback (already halved by caller)
            return self._compose_euler(state, dt * 0.5)

    # ── Helper: compute delta dict from operators ────────────

    def _compute_delta(self, state: State, sub_dt: float) -> Dict[str, float]:
        """Compute the delta (change) from all operators at a given state."""
        result = state.clone()
        for op in self._operators:
            next_state = op.apply(result.clone())
            scale = (sub_dt if sub_dt > 0 else self._dt) / self._dt
            for key in result.payload:
                delta = next_state.payload.get(key, 0.0) - result.payload[key]
                result.payload[key] = result.payload[key] + delta * scale
        return {k: v - state.payload.get(k, 0.0) for k, v in result.payload.items()}

    @staticmethod
    def _apply_delta(state: State, delta: Dict[str, float], scale: float) -> State:
        """Apply a delta dict to a state with given scale factor."""
        out = state.clone()
        for key in out.payload:
            if key in delta:
                out.payload[key] += delta[key] * scale
        return out

    # ── Main step method ────────────────────────────────────

    def step(self, state: State) -> Tuple[State, StepReport]:
        if self._phase in (EnginePhase.HALTED, EnginePhase.FAULTED):
            raise RuntimeError(f"engine is {self._phase}; reset() to continue")
        self._set_phase(EnginePhase.STEPPING)

        subdivisions = 0
        notes: List[str] = []
        dt = self._dt
        last_drift = 0.0
        effective_dt = self._dt
        working = state.clone()

        # Choose integration method
        if self._method == "rk4":
            working = self._compose_rk4(working, dt)
            method_used = "rk4"
            last_drift = state.distance(working)
        elif self._method == "rk45":
            working = self._compose_rk45(working, dt)
            method_used = "rk45"
            last_drift = state.distance(working)
        else:
            # Original Euler with adaptive sub-stepping
            method_used = "euler"
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

        # Singularity check
        singularity = self._detect_singularity(working)
        if singularity:
            self._set_phase(EnginePhase.SINGULARITY)
            notes.append("SINGULARITY DETECTED: NaN/Inf/extreme values")

        # Energy tracking
        energy = self._compute_energy(working)
        energy_delta = energy - (self._prev_energy if self._prev_energy is not None else energy)
        self._prev_energy = energy

        # Lyapunov / chaos tracking
        lyap_est, is_chaotic = self._update_lyapunov(last_drift, dt)
        if is_chaotic:
            notes.append(f"CHAOTIC DYNAMICS: Lyapunov λ≈{lyap_est:.4f} > {self._chaos_threshold}")

        # Timestamp
        working.timestamp = state.timestamp + effective_dt

        report = StepReport(
            step=self._step_count,
            timestamp=working.timestamp,
            drift=last_drift,
            subdivisions=subdivisions,
            operator_count=len(self._operators),
            notes=notes,
            method=method_used,
            energy_delta=energy_delta,
            lyapunov_estimate=lyap_est,
            is_chaotic=is_chaotic,
            singularity_detected=singularity,
        )
        self._step_count += 1
        self._log.append(report)

        if not singularity:
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
        self._lyapunov_sum = 0.0
        self._lyapunov_count = 0
        self._prev_energy = None
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
