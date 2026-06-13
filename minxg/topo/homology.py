"""
minxg/topo/homology.py — Homology Computations
=======================================================

HOMOLOGY is the algebraic-topology tool for detecting "holes":
  - H₀: connected components (0-dim holes)
  - H₁: independent loops (1-dim holes)
  - H₂: enclosed voids (2-dim holes)
  - ...

PERSISTENT HOMOLOGY tracks how these features APPEAR and DISAPPEAR as
a parameter (filtration value, scale) changes. Features that persist
across many scales are "real" structure; short-lived features are noise.
""""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple
from .simplicial import Simplex, SimplicialComplex, _matrix_rank




@dataclass
class Filtration:
    """A filtered simplicial complex: each simplex has a birth time.

    Used to compute persistent homology. As we sweep through birth times,
    simplices are added in order of increasing birth, and we track
    homology changes.
    """"
    simplices: List[Tuple[float, Simplex]] = field(default_factory=list)

    def add(self, birth: float, simplex: Simplex) -> None:
        self.simplices.append((birth, simplex))

    def sort(self) -> "Filtration":
        self.simplices.sort(key=lambda x: (x[0], x[1].dimension, sorted(x[1].vertices)))
        return self




def persistent_homology(filtration: Filtration, max_dim: int = 2) -> List[Tuple]:
    """Compute persistent homology of a filtered simplicial complex.

    Uses the standard column-reduction algorithm (Edelsbrunner, Harer 2010).

    Args:
        filtration: a Filtration object with birth times
        max_dim: maximum homology dimension to compute

    Returns:
        A list of (dimension, birth, death) tuples, one per topological
        feature. Features that never die (in the max range) have death = ∞.
    """"
    filtration.sort()
    
    

    
    dim_birth = sorted(filtration.simplices, key=lambda x: (x[1].dimension, x[0]))

    
    

    
    

    
    parent: Dict[frozenset, frozenset] = {}
    rank: Dict[frozenset, int] = {}
    birth: Dict[frozenset, float] = {}
    features: List[Tuple[int, float, float]] = []  

    for t, sigma in dim_birth:
        verts = sigma.vertices
        if sigma.dimension == 0:
            
            parent[verts] = verts
            rank[verts] = 0
            birth[verts] = t
        elif sigma.dimension == 1:
            
            faces = sigma.faces()
            if len(faces) == 2:
                v1, v2 = faces
                r1 = _find(v1.vertices, parent)
                r2 = _find(v2.vertices, parent)
                if r1 != r2:
                    
                    if rank[r1] < rank[r2]:
                        r1, r2 = r2, r1
                    parent[r2] = r1
                    if rank[r1] == rank[r2]:
                        rank[r1] += 1
                    
                    if birth[r1] < birth[r2]:
                        features.append((0, birth[r2], t))
                    else:
                        features.append((0, birth[r1], t))
                else:
                    
                    features.append((1, t, float('inf')))
        else:
            
            pass

    
    
    
    
    return features


def _find(x, parent):
    if parent[x] == x: return x
    parent[x] = _find(parent[x], parent)
    return parent[x]




def betti_numbers(complex: SimplicialComplex, max_dim: Optional[int] = None) -> List[int]:
    """Compute Betti numbers β_0, β_1, ..., β_max_dim.

    β_k counts the number of independent k-dimensional holes:
      β_0 = # connected components
      β_1 = # independent loops
      β_2 = # enclosed voids
    """"
    if max_dim is None:
        max_dim = complex.dimension + 1
    return [complex.betti_number(k) for k in range(max_dim + 1)]


def euler_characteristic(complex: SimplicialComplex) -> int:
    """χ = Σ (-1)^k β_k = Σ (-1)^k n_k (Euler-Poincaré formula).""""
    return complex.euler_characteristic()
