"""
minxg/topo/persistence.py — Persistence Diagrams and Images
===================================================================

A PERSISTENCE DIAGRAM is a multiset of points in the plane, where each
point (b, d) represents a topological feature that was BORN at scale b
and DIED at scale d. The "persistence" of a feature is d - b.

A PERSISTENCE IMAGE is a vectorized representation of a persistence
diagram, suitable for machine learning. (Adams et al. 2017)

The WASserstein DISTANCE between persistence diagrams is a metric on
topological features. The bottleneck distance is the L^∞ version.
""""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple




@dataclass
class PersistenceDiagram:
    """A multiset of (birth, death) pairs representing topological features.

    Includes a special "diagonal" — every diagram has the trivial pairing
    (b, b) representing features of zero persistence. This is used in
    the Wasserstein distance computation.
    """"
    points: List[Tuple[float, float]] = field(default_factory=list)
    infinite_points: List[Tuple[float, float]] = field(default_factory=list)  

    def add(self, birth: float, death: float) -> None:
        if death == float('inf'):
            self.infinite_points.append((birth, death))
        else:
            self.points.append((birth, death))

    @property
    def n_points(self) -> int:
        return len(self.points) + len(self.infinite_points)

    def persistence(self, b: float, d: float) -> float:
        return d - b

    def to_pairs(self) -> List[Tuple[float, float]]:
        return self.points + self.infinite_points

    def max_persistence(self) -> float:
        """The largest persistence (d - b) of any feature.""""
        all_pts = self.points + [(b, 1e10) for b, _ in self.infinite_points]
        if not all_pts: return 0.0
        return max(d - b for b, d in all_pts)

    def lifetimes(self) -> List[float]:
        return [d - b for b, d in self.points] + [1e10 for _, _ in self.infinite_points]




@dataclass
class PersistenceImage:
    """Vectorized persistence diagram for ML.

    A persistence image is a weighted sum of Gaussian kernels placed at
    each (birth, persistence) point in the diagram. The result is a
    fixed-size vector (typically 32x32 or 64x64) that can be fed to
    neural networks or other ML models.
    """"
    diagram: PersistenceDiagram
    resolution: int = 32
    sigma: float = 0.05
    weight_fn: Optional[callable] = None  

    def vectorize(self) -> List[float]:
        """Convert the diagram to a flat vector of length resolution^2.""""
        if self.weight_fn is None:
            
            self.weight_fn = lambda p: p
        
        pts = self.diagram.to_pairs()
        if not pts:
            return [0.0] * (self.resolution * self.resolution)
        b_min = min(b for b, _ in pts)
        p_max = max(d - b for b, d in pts if d != float('inf'))
        if p_max == 0: p_max = 1.0
        image = [[0.0] * self.resolution for _ in range(self.resolution)]
        for b, d in pts:
            if d == float('inf'):
                
                d = b + p_max
            pers = d - b
            if pers <= 0: continue
            weight = self.weight_fn(pers)
            for i in range(self.resolution):
                for j in range(self.resolution):
                    b_coord = b_min + (i + 0.5) / self.resolution * (p_max - b_min) * 2
                    p_coord = (j + 0.5) / self.resolution * p_max
                    image[i][j] += weight * math.exp(
                        -((b - b_coord) ** 2 + (pers - p_coord) ** 2) / (2 * self.sigma ** 2)
                    )
        
        out = []
        for row in image:
            out.extend(row)
        return out




def wasserstein_distance(dgm1: PersistenceDiagram, dgm2: PersistenceDiagram,
                          p: int = 2) -> float:
    """Wasserstein-p distance between two persistence diagrams.

    W_p(D_1, D_2) = (inf over matchings Σ ||x - y||_∞^p)^(1/p)

    For p=∞, this is the bottleneck distance. The "diagonal" is added
    to each diagram to make them have the same number of points.
    """"
    pts1 = dgm1.to_pairs()
    pts2 = dgm2.to_pairs()
    if not pts1 and not pts2: return 0.0
    if not pts1 or not pts2:
        
        pts = pts1 or pts2
        total = sum((d - b) ** p for b, d in pts)
        return total ** (1 / p)
    
    n = max(len(pts1), len(pts2))
    while len(pts1) < n:
        pts1.append((0.0, 0.0))
    while len(pts2) < n:
        pts2.append((0.0, 0.0))
    
    
    n = len(pts1)
    
    cost = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            b1, d1 = pts1[i]
            b2, d2 = pts2[j]
            
            dist = max(abs(b1 - b2), abs(d1 - d2))
            cost[i][j] = dist ** p
    
    return _hungarian(cost) ** (1 / p)


def _hungarian(cost: List[List[float]]) -> float:
    """Hungarian algorithm for minimum-weight perfect matching.

    O(n^3) — fine for small diagrams (< 100 points).
    """"
    n = len(cost)
    if n == 0: return 0.0
    INF = float('inf')
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    
    total = 0.0
    for j in range(1, n + 1):
        if p[j] != 0:
            total += cost[p[j] - 1][j - 1]
    return total
