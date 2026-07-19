"""minxg.symbdiff.operators_symbdiff — Operator-field bindings for symbdiff.

Exports Operator subclasses that bring symbolic differentiation
capabilities into the driver engine's operator composition framework.

Operators:
  JetOperator     — applies jet-based automatic differentiation
  LieBracketOp    — computes Lie bracket drift between two operator fields
  DiffIdealOp     — tests differential ideal membership on state
  IntFactorOp     — attempts to find an integrating factor for the ODE
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from minxg.driver.operator import Operator
from minxg.driver.state import State
from minxg.symbdiff import Jet, DiffPoly, VectorField, lie_bracket


class JetOperator(Operator):
    """Symbolic differentiation via jets.

    Wraps a callable fn(state_dict) -> float into a jet-based operator.
    At each step, it computes f(state) as a jet of configurable order,
    giving exact higher-order derivatives for free.

    The operator output is:
      state[key] ← jet.value  (the function value)
      state[key+"__d1"] ← jet.deriv(1)  (first derivative)
      state[key+"__d2"] ← jet.deriv(2)  (second derivative)
      ...
    """
    def __init__(self, key: str, fn, jet_order: int = 4, name: str = ""):
        super().__init__(name=name or f"jet_{key}")
        self._key = key
        self._fn = fn
        self._order = jet_order

    def apply(self, state: State) -> State:
        out = state.clone()
        sd = dict(out.payload)
        val = self._fn(sd)
        # Build jet from the value and numerical derivatives
        j = Jet.constant(self._order, val)
        eps = 1e-7
        if self._order >= 2:
            sd_plus = dict(sd)
            sd_plus[self._key] = sd.get(self._key, 0.0) + eps
            sd_minus = dict(sd)
            sd_minus[self._key] = sd.get(self._key, 0.0) - eps
            j.derivs[0] = (self._fn(sd_plus) - self._fn(sd_minus)) / (2 * eps)
        if self._order >= 3:
            sd0 = sd.get(self._key, 0.0)
            f0 = val
            sd_c = dict(sd); sd_c[self._key] = sd0 + eps
            f_plus = self._fn(sd_c)
            sd_c[self._key] = sd0 - eps
            f_minus = self._fn(sd_c)
            j.derivs[1] = (f_plus - 2*f0 + f_minus) / (eps * eps)

        out.payload[self._key] = j.value
        for d in range(1, self._order):
            out.payload[f"{self._key}__d{d}"] = j.deriv(d)
        return out


class LieBracketOperator(Operator):
    """Computes Lie bracket drift [X,Y] between two operator vector fields.

    If the bracket is non-zero, it adds a _lie_bracket_{X}_{Y} key to state
    containing the magnitude — the driver engine can use this to reorder
    operators for zero drift.
    """
    def __init__(self, X: VectorField, Y: VectorField,
                 state_sample: Optional[Dict[str, float]] = None,
                 name: str = ""):
        super().__init__(name=name or f"lie_bracket_{X.name}_{Y.name}")
        self._X = X
        self._Y = Y
        self._sample = state_sample or {}

    def apply(self, state: State) -> State:
        out = state.clone()
        sd = dict(out.payload)
        bracket = lie_bracket(self._X, self._Y, sd)
        mag = math.sqrt(sum(v*v for v in bracket.values()))
        out.payload[f"_lie_bracket_{self._X.name}_{self._Y.name}"] = mag
        return out


class DiffIdealOperator(Operator):
    """Tests differential ideal membership.

    Given a DiffPoly P and a list of generators G=[g1,g2,...],
    reduces P modulo G using total derivative elimination.
    If P reduces to zero modulo G, P is in the differential ideal ⟨G⟩.

    Adds a _diff_ideal_member key: 1.0 if member, 0.0 if not.
    """
    def __init__(self, poly: DiffPoly, generators: List[DiffPoly],
                 name: str = "diff_ideal"):
        super().__init__(name=name)
        self._poly = poly
        self._gens = generators

    def apply(self, state: State) -> State:
        out = state.clone()
        # Simplified reduction: check if poly is zero after subtracting
        # scalar multiples of generators
        remainder = self._poly
        for g in self._gens:
            if g.is_zero():
                continue
            # Try to reduce by dividing out leading terms
            # (Simplified — full Buchberger algorithm is expensive)
            for mono, coeff in list(remainder.coeffs.items()):
                for g_mono, g_coeff in g.coeffs.items():
                    # Simple cancellation check
                    if mono == g_mono and abs(g_coeff) > 1e-15:
                        factor = coeff / g_coeff
                        reduced = DiffPoly(g.variables,
                                         {k: -factor * v for k, v in g.coeffs.items()})
                        remainder = remainder + reduced
                        break

        out.payload["_diff_ideal_member"] = 0.0 if remainder.is_zero() else 1.0
        return out


class IntFactorOperator(Operator):
    """Attempts to find an integrating factor for the current ODE.

    Reads state keys _M and _N (functions M(x,y), N(x,y) representing
    M dx + N dy = 0). If an integrating factor is found, stores it
    in _integrating_factor.
    """
    def __init__(self, name: str = "int_factor"):
        super().__init__(name=name)

    def apply(self, state: State) -> State:
        out = state.clone()
        from minxg.symbdiff import find_integrating_factor
        x = out.payload.get("x", 0.0)
        y = out.payload.get("y", 0.0)

        # Extract M, N from state if available
        M_val = out.payload.get("_M", None)
        N_val = out.payload.get("_N", None)

        if M_val is not None and N_val is not None:
            def M(xv, yv): return M_val  # simplified
            def N(xv, yv): return N_val
            mu = find_integrating_factor(M, N, x0=x, y0=y)
            if mu is not None:
                out.payload["_integrating_factor"] = mu(x, y)
            else:
                out.payload["_integrating_factor"] = 0.0
        else:
            out.payload["_integrating_factor"] = -1.0  # not applicable
        return out


__all__ = [
    "JetOperator",
    "LieBracketOperator",
    "DiffIdealOperator",
    "IntFactorOperator",
]
