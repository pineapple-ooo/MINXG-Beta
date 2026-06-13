"""
minxg/fiber/tangent.py — Tangent Bundle
================================================

The TANGENT BUNDLE T(M) of a manifold M is the vector bundle whose
fiber at each point p ∈ M is the tangent space T_p M.

For an n-dimensional manifold:
  - T(M) is a 2n-dimensional manifold
  - T_p M is an n-dimensional vector space
  - A vector field is a section of T(M)
  - A 1-form is a section of T*(M) (cotangent bundle)

For a Riemannian manifold, T(M) comes with:
  - The Riemannian metric g
  - The Levi-Civita connection
  - The Riemann curvature tensor
  - Geodesics
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from .bundle import VectorBundle
from .connection import Connection


@dataclass
class RiemannianMetric:
    """A Riemannian metric g: T(M) × T(M) → R.

    At each point of the manifold, g is a positive-definite symmetric
    bilinear form on the tangent space.
    """
    metric_fn: Callable[[List[float]], List[List[float]]]

    def at(self, point: List[float]) -> List[List[float]]:
        return self.metric_fn(point)

    def inner(self, u: List[float], v: List[float], point: List[float]) -> float:
        g = self.at(point)
        n = len(u)
        return sum(g[i][j] * u[i] * v[j] for i in range(n) for j in range(n))

    def norm(self, v: List[float], point: List[float]) -> float:
        return math.sqrt(max(0, self.inner(v, v, point)))

    def distance_infinitesimal(self, v: List[float], point: List[float]) -> float:
        return self.norm(v, point)


class TangentBundle(VectorBundle):
    """The tangent bundle T(M) of a Riemannian manifold M.

    Provides:
    - Metric
    - Levi-Civita connection (torsion-free, metric-compatible)
    - Riemann curvature
    - Geodesics
    """
    def __init__(self, dim: int, metric: RiemannianMetric):
        super().__init__(dim, dim, metric.at([0.0] * dim))
        self.metric = metric
        self.dim = dim
        self._levi_civita_cache: dict = {}

    def levi_civita(self, point: List[float], eps: float = 1e-5) -> List[List[List[float]]]:
        """Compute the Levi-Civita Christoffel symbols at a point.

        Γ^i_jk = (1/2) g^il (∂_j g_lk + ∂_k g_jl - ∂_l g_jk)
        """
        key = tuple(round(x, 5) for x in point)
        if key in self._levi_civita_cache:
            return self._levi_civita_cache[key]
        n = self.dim
        # Compute metric inverse at this point
        g = self.metric.at(point)
        # ... Gauss-Jordan to invert
        aug = [row + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(g)]
        for col in range(n):
            pivot = col
            for row in range(col + 1, n):
                if abs(aug[row][col]) > abs(aug[pivot][col]):
                    pivot = row
            aug[col], aug[pivot] = aug[pivot], aug[col]
            pv = aug[col][col]
            for j in range(2 * n):
                aug[col][j] /= pv
            for row in range(n):
                if row == col: continue
                factor = aug[row][col]
                for j in range(2 * n):
                    aug[row][j] -= factor * aug[col][j]
        g_inv = [row[n:] for row in aug]

        # Partial derivatives of metric
        def d_g(i, j, axis):
            bp = list(point); bp[axis] += eps
            bm = list(point); bm[axis] -= eps
            g_p = self.metric.at(bp)
            g_m = self.metric.at(bm)
            return (g_p[i][j] - g_m[i][j]) / (2 * eps)

        # Christoffel symbols
        Gamma = [[[0.0] * n for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    s = 0.0
                    for l in range(n):
                        s += g_inv[i][l] * (d_g(l, k, j) + d_g(j, l, k) - d_g(j, k, l))
                    Gamma[i][j][k] = 0.5 * s
        self._levi_civita_cache[key] = Gamma
        return Gamma

    def geodesic(self, initial_point: List[float], initial_velocity: List[float],
                 t_max: float = 1.0, n_steps: int = 100) -> List[List[float]]:
        """Compute a geodesic (shortest path) starting at initial_point
        with initial velocity.

        Returns the trajectory of points along the geodesic.
        """
        traj = [list(initial_point)]
        x = list(initial_point)
        v = list(initial_velocity)
        dt = t_max / n_steps
        for _ in range(n_steps):
            Gamma = self.levi_civita(x)
            dx = [v[k] * dt for k in range(len(v))]
            dv = [0.0] * len(v)
            for i in range(len(v)):
                for j in range(len(v)):
                    for k in range(len(v)):
                        dv[i] -= Gamma[i][j][k] * v[j] * v[k] * dt
            x = [x[k] + dx[k] for k in range(len(x))]
            v = [v[k] + dv[k] for k in range(len(v))]
            traj.append(list(x))
        return traj

    def exponential_map(self, base_point: List[float], velocity: List[float],
                       t: float = 1.0, n_steps: int = 100) -> List[float]:
        """Exponential map at base_point: exp_p(t·v)."""
        return self.geodesic(base_point, velocity, t, n_steps)[-1]
