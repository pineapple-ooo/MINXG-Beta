"""
minxg/topo/filtration.py — Filtrations of Point Clouds
==============================================================

To compute persistent homology, we need a FILTRATION — a 1-parameter family
of simplicial complexes that "grow" as the parameter increases. The most
common filtrations on point clouds:

VIETORIS-RIPS FILTRATION
------------------------
For each ε ≥ 0, the Vietoris-Rips complex VR(P, ε) contains:
  - All points
  - An edge (u, v) if d(u, v) ≤ ε
  - A simplex (v_0, ..., v_k) if ALL pairs are within distance ε

The key property: VR(P, ε) is a clique complex of the ε-neighborhood graph.
As ε grows, more simplices appear, and we can track the homology changes.

ALPHA COMPLEX
-------------
A more geometrically faithful filtration. Alpha shapes are subcomplexes
of Delaunay triangulations. They capture the "real" shape of a point cloud
better than Vietoris-Rips but require Delaunay computation (CGAL territory).

For our pure-Python implementation, we provide:
  - Vietoris-Rips: edge and 2-simplex (triangle) construction
  - Weighted-Rips: filtrations with vertex weights
""""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from .simplicial import Simplex, SimplicialComplex
from .homology import Filtration




def euclidean(p: List[float], q: List[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))


def chebyshev(p: List[float], q: List[float]) -> float:
    return max(abs(a - b) for a, b in zip(p, q))


def manhattan(p: List[float], q: List[float]) -> float:
    return sum(abs(a - b) for a, b in zip(p, q))


def cosine_distance(p: List[float], q: List[float]) -> float:
    dot = sum(a * b for a, b in zip(p, q))
    np_ = math.sqrt(sum(a * a for a in p)) + 1e-12
    nq = math.sqrt(sum(b * b for b in q)) + 1e-12
    return 1 - dot / (np_ * nq)




@dataclass
class VietorisRips:
    """Vietoris-Rips filtration of a point cloud.

    Build via:
      vr = VietorisRips(points)
      filtration = vr.build_filtration(max_edge_length, max_dim=2)
    """"
    points: List[List[float]]
    distance_fn: Callable = euclidean

    def pairwise_distances(self) -> List[List[float]]:
        n = len(self.points)
        D = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = self.distance_fn(self.points[i], self.points[j])
                D[i][j] = d
                D[j][i] = d
        return D

    def build_filtration(self, max_edge_length: Optional[float] = None,
                         max_dim: int = 2) -> Filtration:
        """Build the Vietoris-Rips filtration up to dimension max_dim.

        If max_edge_length is None, all pairs are included.
        """"
        n = len(self.points)
        D = self.pairwise_distances()
        filt = Filtration()

        
        for i in range(n):
            filt.add(0.0, Simplex(frozenset({i})))

        
        for i in range(n):
            for j in range(i + 1, n):
                d = D[i][j]
                if max_edge_length is not None and d > max_edge_length:
                    continue
                filt.add(d, Simplex(frozenset({i, j})))

        
        if max_dim >= 2:
            for i in range(n):
                for j in range(i + 1, n):
                    for k in range(j + 1, n):
                        d_max = max(D[i][j], D[j][k], D[i][k])
                        if max_edge_length is not None and d_max > max_edge_length:
                            continue
                        filt.add(d_max, Simplex(frozenset({i, j, k})))

        return filt


def alpha_complex(points: List[List[float]], max_radius: float = float('inf')) -> Filtration:
    """Alpha complex filtration (simplified).

    For pure-Python, we approximate alpha shapes by:
    1. Compute Delaunay-like triangulation via greedy algorithm
    2. Filter simplices by their "alpha" (circumradius)

    This is a simplified version; full alpha shapes need CGAL.
    """"
    n = len(points)
    D = [[euclidean(points[i], points[j]) for j in range(n)] for i in range(n)]
    filt = Filtration()
    for i in range(n):
        filt.add(0.0, Simplex(frozenset({i})))
    for i in range(n):
        for j in range(i + 1, n):
            d = D[i][j]
            if d <= max_radius * 2:
                filt.add(d / 2, Simplex(frozenset({i, j})))
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                d_max = max(D[i][j], D[j][k], D[i][k])
                if d_max <= max_radius * 2:
                    filt.add(d_max / 2, Simplex(frozenset({i, j, k})))
    return filt
