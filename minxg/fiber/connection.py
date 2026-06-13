"""
minxg/fiber/connection.py — Connections, Parallel Transport, Curvature
==============================================================================

A CONNECTION on a fiber bundle is a rule for "comparing fibers at
different points" — equivalent to a way to define the COVARIANT DERIVATIVE
of sections. The connection is the key object in gauge theory.

PARALLEL TRANSPORT moves a vector along a curve in the base space
WITHOUT CHANGING it (relative to the connection). On a curved manifold,
a "constant" vector changes direction when transported around a loop —
this is the HOLONOMY, related to the curvature by:

  Holonomy(γ) = P exp(∮_γ ω) ≈ 1 + ∫∫_S F

where F is the curvature 2-form.

CURVATURE F = dω + (1/2)[ω, ω] is the "exterior covariant derivative" of
the connection. For a flat bundle, F = 0. For a non-trivial bundle
(e.g., sphere), F ≠ 0.
""""
from __future__ import annotations
import math
from typing import Callable, List, Optional, Tuple
from .bundle import VectorBundle, FiberBundle


class Connection:
    """A connection on a vector bundle, specified by connection 1-forms.

    For each base coordinate x^i, the connection 1-form ω is an
    n×n matrix (where n is the fiber dimension):
      ω = Σ_i Γ^i dx^i

    The Christoffel symbols Γ^i_jk define how the i-th component of
    a section changes when we move in the k direction.
    """"
    def __init__(self, dim: int, christoffel_fn: Optional[Callable] = None):
        self.dim = dim
        self._christoffel_fn = christoffel_fn
        
        self._cache: dict = {}

    def christoffel(self, base_point: List[float]) -> List[List[List[float]]]:
        """Get the Christoffel symbols at the given base point.

        Returns a 3-tensor Γ where Γ[i][j][k] = connection coefficient
        for the i-th fiber component, in the j-th base direction,
        with respect to the k-th fiber basis vector.

        Default: zero connection (trivial).
        """"
        key = tuple(round(x, 6) for x in base_point)
        if key in self._cache:
            return self._cache[key]
        if self._christoffel_fn is not None:
            result = self._christoffel_fn(base_point)
        else:
            result = [[[0.0] * self.dim for _ in range(self.dim)] for _ in range(self.dim)]
        self._cache[key] = result
        return result


class ParallelTransport:
    """Parallel transport along a curve on the base.

    Solves the ODE:
      dV^i/dt = -Γ^i_jk V^j (dx^k/dt)

    where Γ are the Christoffel symbols of the connection.
    """"
    def __init__(self, connection: Connection, curve_fn: Callable[[float], List[float]],
                 t_min: float = 0.0, t_max: float = 1.0):
        self.connection = connection
        self.curve = curve_fn
        self.t_min = t_min
        self.t_max = t_max

    def transport(self, initial_vector: List[float], n_steps: int = 100) -> List[float]:
        """Transport initial_vector along the curve from t_min to t_max.""""
        v = list(initial_vector)
        dt = (self.t_max - self.t_min) / n_steps
        for step in range(n_steps):
            t = self.t_min + step * dt
            t_next = t + dt
            
            base = self.curve(t)
            base_next = self.curve(t_next)
            dtheta = [b2 - b1 for b1, b2 in zip(base, base_next)]
            Gamma = self.connection.christoffel(base)
            dv = [0.0] * len(v)
            for i in range(len(v)):
                for j in range(len(v)):
                    for k in range(len(dtheta)):
                        dv[i] -= Gamma[i][j][k] * v[j] * dtheta[k]
            v = [v[i] + dv[i] for i in range(len(v))]
        return v

    def holonomy(self, initial_vector: List[float], n_steps: int = 200) -> List[float]:
        """Compute the holonomy (parallel transport around a closed loop).

        The initial vector is transported along the closed curve and
        the result is compared to the start.
        """"
        transported = self.transport(initial_vector, n_steps)
        return [t - i for t, i in zip(transported, initial_vector)]


class Curvature:
    """The curvature 2-form of a connection.

    F^i_j = dω^i_j + ω^i_k ∧ ω^k_j
         = ∂_k Γ^i_jl dx^k ∧ dx^l + Γ^i_km Γ^m_jl dx^k ∧ dx^l

    In coordinates:
      F^i_jkl = ∂_k Γ^i_jl - ∂_l Γ^i_jk + Γ^i_km Γ^m_jl - Γ^i_lm Γ^m_jk

    F = 0 iff the connection is flat.
    """"
    def __init__(self, connection: Connection, n_dim: Optional[int] = None):
        self.connection = connection
        self.n_dim = n_dim or connection.dim

    def component(self, i: int, j: int, k: int, l: int,
                  base_point: List[float], eps: float = 1e-4) -> float:
        """Compute one component of the curvature tensor F^i_jkl.""""
        def Gamma(base):
            return self.connection.christoffel(base)

        def partial_Gamma(i, j, k, axis, base):
            
            bp = list(base); bp[axis] += eps
            bm = list(base); bm[axis] -= eps
            Gp = Gamma(bp)
            Gm = Gamma(bm)
            return (Gp[i][j][k] - Gm[i][j][k]) / (2 * eps)

        
        G = Gamma(base_point)
        term1 = partial_Gamma(i, j, l, k, base_point) - partial_Gamma(i, j, k, l, base_point)
        term2 = sum(G[i][m][k] * G[m][j][l] for m in range(self.n_dim))
        term3 = sum(G[i][m][l] * G[m][j][k] for m in range(self.n_dim))
        return term1 + term2 - term3

    def riemann_tensor(self, base_point: List[float]) -> List[List[List[List[float]]]]:
        """Compute the full Riemann tensor R^i_jkl at a point.""""
        n = self.n_dim
        R = [[[[0.0] * n for _ in range(n)] for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    for l in range(n):
                        R[i][j][k][l] = self.component(i, j, k, l, base_point)
        return R

    def ricci_tensor(self, base_point: List[float]) -> List[List[float]]:
        """Ricci tensor R_jl = R^i_jil (contract over i and k).""""
        R = self.riemann_tensor(base_point)
        n = self.n_dim
        Ric = [[0.0] * n for _ in range(n)]
        for j in range(n):
            for l in range(n):
                Ric[j][l] = sum(R[i][j][i][l] for i in range(n))
        return Ric

    def scalar_curvature(self, base_point: List[float],
                        metric: Optional[List[List[float]]] = None,
                        metric_inv: Optional[List[List[float]]] = None) -> float:
        """Scalar curvature R = g^jl R_jl (using metric inverse).""""
        Ric = self.ricci_tensor(base_point)
        n = self.n_dim
        if metric_inv is None:
            if metric is None:
                
                metric_inv = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
            else:
                
                m = list(metric)
                aug = [row + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
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
                metric_inv = [row[n:] for row in aug]
        
        total = 0.0
        for j in range(n):
            for l in range(n):
                total += metric_inv[j][l] * Ric[j][l]
        return total
