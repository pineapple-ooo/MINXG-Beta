"""
minxg/fiber/frame.py — Frame Bundle, Vielbein, Spinning
===============================================================

The FRAME BUNDLE F(M) of an n-dimensional manifold M is the principal
GL(n) (or SO(n) for oriented Riemannian) bundle whose fiber at each
point is the set of all bases (frames) for the tangent space.

A VIELBEIN (German for "many legs") is a section of the frame bundle
— a choice of orthonormal basis at each point. In general relativity,
the vielbein e^a_μ (or tetrad for n=4) is used to convert between
curved indices (μ) and flat indices (a).

The frame bundle is the natural setting for:
  - SPIN STRUCTURES (needed to define spinors on curved manifolds)
  - CARTAN'S MOVING FRAME (a way to compute curvature)
  - GAUGE THEORIES (where the frame is the gauge field)
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Callable, List, Optional
from .bundle import PrincipalBundle
from .tangent import TangentBundle, RiemannianMetric


@dataclass
class Vielbein:
    """A vielbein (orthonormal frame field) on a manifold.

    e^a_μ: at each point, gives an orthonormal basis {e_0, e_1, ...} for T_p M.
    The flat index 'a' labels the basis vector; the curved index 'μ' is the
    coordinate in the basis.
    """
    vielbein_fn: Callable[[List[float]], List[List[float]]]
    inverse_fn: Optional[Callable[[List[float]], List[List[float]]]] = None

    def at(self, point: List[float]) -> List[List[float]]:
        return self.vielbein_fn(point)

    def inverse(self, point: List[float]) -> List[List[float]]:
        if self.inverse_fn is not None:
            return self.inverse_fn(point)
        # Compute via Gauss-Jordan
        e = self.vielbein_fn(point)
        n = len(e)
        aug = [row + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(e)]
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
        return [row[n:] for row in aug]


def vielbein(point: List[float], metric: RiemannianMetric) -> Vielbein:
    """Build a vielbein at a point by Gram-Schmidt orthogonalization.

    For a Euclidean metric, the vielbein is just the identity (after
    orthogonalization). For non-trivial metrics, the vielbein encodes
    the metric structure.
    """
    n = len(point)
    g = metric.at(point)
    # Gram-Schmidt
    e = [[0.0] * n for _ in range(n)]
    # Use the metric as a guide
    for i in range(n):
        # Start with e_i
        e[i][i] = 1.0
        # Subtract projections onto previous vectors
        for j in range(i):
            dot = sum(g[k][l] * e[i][k] * e[j][l] for k in range(n) for l in range(n))
            for k in range(n):
                e[i][k] -= dot * e[j][k]
        # Normalize
        norm_sq = sum(g[k][l] * e[i][k] * e[i][l] for k in range(n) for l in range(n))
        norm = math.sqrt(max(norm_sq, 1e-12))
        for k in range(n):
            e[i][k] /= norm
    return Vielbein(lambda p: e)  # constant for now


class FrameBundle(PrincipalBundle):
    """The frame bundle of a manifold.

    The fiber at each point p is the set of all bases (frames) of T_p M.
    A vielbein is a global section.
    """
    def __init__(self, base_dim: int, group: str = "GL"):
        super().__init__(base_dim, base_dim * base_dim, group + f"({base_dim})")

    def orthonormal_frame(self, point: List[float], metric: RiemannianMetric) -> Vielbein:
        """Construct an orthonormal frame at the point."""
        return vielbein(point, metric)
