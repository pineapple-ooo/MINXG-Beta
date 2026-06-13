"""
minxg/chaos/lyapunov.py — Lyapunov Exponents
====================================================

The LYAPUNOV EXPONENT λ measures the rate at which nearby trajectories
diverge:
  |δ(t)| ≈ |δ(0)| · e^(λ·t)

- λ > 0: chaotic (exponential divergence)
- λ = 0: marginally stable (limit cycle)
- λ < 0: stable fixed point (exponential convergence)

For 1D maps: λ = lim (1/n) Σ log|f'(x_i)|
For 2D+ maps: there are multiple exponents (Lyapunov SPECTRUM), sum = -Λ (Lyapunov)
"""
from __future__ import annotations
import math
from typing import Callable, List, Tuple


def lyapunov_exponent(f: Callable[[float], float], f_prime: Callable[[float], float],
                       x0: float, n: int = 10000, transient: int = 1000) -> float:
    """Compute the largest Lyapunov exponent for a 1D map.

    λ = lim_{n→∞} (1/n) Σ_{i=0}^{n-1} log|f'(x_i)|

    Args:
        f: the map x_{n+1} = f(x_n)
        f_prime: the derivative f'(x)
        x0: initial condition
        n: number of iterations
        transient: iterations to discard (let the trajectory settle on attractor)
    """
    x = x0
    for _ in range(transient):
        x = f(x)
    total = 0.0
    count = 0
    for _ in range(n):
        x = f(x)
        deriv = abs(f_prime(x))
        if deriv > 0:
            total += math.log(deriv)
            count += 1
    return total / max(count, 1)


def lyapunov_spectrum(orbit_fn: Callable[[List[float]], List[float]],
                       dim: int, x0: List[float], n: int = 10000,
                       transient: int = 100, dt: float = 1e-8) -> List[float]:
    """Compute the full Lyapunov spectrum for a d-dimensional map.

    Uses the standard algorithm: maintain d nearby trajectories perturbed
    along d orthogonal directions, periodically re-orthogonalize.
    """
    # For maps, use Benettin's algorithm
    x = list(x0)
    Q = [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]
    log_stretches = [[] for _ in range(dim)]

    # Transient
    for _ in range(transient):
        x = orbit_fn(x)

    for _ in range(n):
        # Evolve the orbit
        x = orbit_fn(x)
        # Evolve the tangent vectors (for maps, just apply the Jacobian)
        # Without explicit Jacobian, finite differences
        for j in range(dim):
            x_pert = [x[k] + dt * Q[k][j] for k in range(dim)]
            x_pert = orbit_fn(x_pert)
            for i in range(dim):
                Q[i][j] = (x_pert[i] - x[i]) / dt
        # Gram-Schmidt orthogonalize
        for j in range(dim):
            # Subtract projections onto previous vectors
            for k in range(j):
                dot = sum(Q[i][j] * Q[i][k] for i in range(dim))
                for i in range(dim):
                    Q[i][j] -= dot * Q[i][k]
            norm = math.sqrt(sum(Q[i][j] ** 2 for i in range(dim)))
            if norm > 0:
                log_stretches[j].append(math.log(norm))
                for i in range(dim):
                    Q[i][j] /= norm

    return [sum(ls) / max(len(ls), 1) / dt for ls in log_stretches]


def logistic_lyapunov(r: float, n: int = 10000) -> float:
    """Lyapunov exponent of the logistic map at parameter r.

    The Feigenbaum-Coullet-Tresser constant: λ changes sign at r ≈ 3.5699.
    """
    f = lambda x: r * x * (1 - x)
    fp = lambda x: r * (1 - 2 * x)
    return lyapunov_exponent(f, fp, 0.5, n=n)
