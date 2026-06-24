"""
minxg/topo/simplicial.py — Simplices and Simplicial Complexes
====================================================================

A k-SIMPLEX is a k-dimensional polytope with k+1 vertices:
  0-simplex: vertex (point)
  1-simplex: edge
  2-simplex: triangle (filled)
  3-simplex: tetrahedron
  ...

A SIMPLICIAL COMPLEX is a collection of simplices closed under taking faces:
if σ is a simplex and τ is a face of σ, then τ is also in the complex.

This is the basic data structure for algebraic topology.
"""
from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Simplex:
    """A k-simplex, identified by its set of vertex IDs.

    Vertices are arbitrary hashable IDs (e.g., strings, integers).
    For an unweighted complex, the simplex is just a frozenset of vertices.
    """
    vertices: FrozenSet[int]  

    @property
    def dimension(self) -> int:
        return len(self.vertices) - 1

    def faces(self) -> List["Simplex"]:
        """All proper faces of this simplex (with dimension one less)."""
        if not self.vertices:
            return []
        return [Simplex(frozenset(self.vertices - {v})) for v in self.vertices]

    def is_face_of(self, other: "Simplex") -> bool:
        """Is self a face of other? I.e., self.vertices ⊂ other.vertices."""
        return self.vertices < other.vertices

    def __lt__(self, other):
        return (self.dimension, sorted(self.vertices)) < (other.dimension, sorted(other.vertices))

    def __repr__(self):
        return f"σ^{self.dimension}{tuple(sorted(self.vertices))}"


@dataclass
class SimplicialComplex:
    """A finite simplicial complex.

    Maintains closure under faces. Adding a simplex automatically adds
    all its faces.
    """
    simplices: Set[Simplex] = field(default_factory=set)
    _vertex_ids: Dict[int, str] = field(default_factory=dict)  

    def add(self, simplex: Simplex) -> None:
        """Add a simplex and all its sub-faces (recursively) to the complex."""
        self._add_recursive(simplex)

    def _add_recursive(self, simplex: Simplex) -> None:
        if simplex.dimension < 0:
            return  
        if simplex in self.simplices:
            return
        self.simplices.add(simplex)
        for face in simplex.faces():
            self._add_recursive(face)

    def add_many(self, simplices: Iterable[Simplex]) -> None:
        for s in simplices:
            self.add(s)

    def count_simplices(self, k: Optional[int] = None) -> int:
        """Count simplices. If k given, only k-dimensional ones."""
        if k is None: return len(self.simplices)
        return sum(1 for s in self.simplices if s.dimension == k)

    @property
    def vertices(self) -> Set[int]:
        """All vertex IDs in the complex."""
        out: Set[int] = set()
        for s in self.simplices:
            out |= set(s.vertices)
        return out

    @property
    def dimension(self) -> int:
        """The maximum dimension of any simplex."""
        if not self.simplices: return -1
        return max(s.dimension for s in self.simplices)

    def n_simplices(self, k: Optional[int] = None) -> int:
        """Count simplices. If k given, only k-dimensional ones."""
        return self.count_simplices(k)

    @property
    def n_simplices_all(self) -> int:
        return len(self.simplices)

    def n_simplices(self, k: Optional[int] = None) -> int:
        """Count simplices. If k given, only k-dimensional ones."""
        return self.count_simplices(k)

    @property
    def n_simplices_all(self) -> int:
        return len(self.simplices)

    def star(self, simplex: Simplex) -> Set[Simplex]:
        """Star of a simplex: all simplices containing it as a face."""
        return {s for s in self.simplices if simplex.is_face_of(s) or simplex == s}

    def link(self, simplex: Simplex) -> "SimplicialComplex":
        """Link of a simplex: simplices in star that don't intersect the interior."""
        link = SimplicialComplex()
        for s in self.star(simplex):
            if s.vertices.isdisjoint(simplex.vertices) or s.vertices == simplex.vertices:
                link.add(Simplex(s.vertices - simplex.vertices))
        return link

    def boundary_matrix(self, k: int) -> List[List[int]]:
        """Boundary matrix ∂_k : C_k → C_(k-1).

        Rows indexed by (k-1)-simplices, columns by k-simplices.
        Entry is ±1 (or 0) depending on whether the (k-1)-simplex is a
        face of the k-simplex and the orientation parity.
        """
        k_simplices = sorted(s for s in self.simplices if s.dimension == k)
        km1_simplices = sorted(s for s in self.simplices if s.dimension == k - 1)
        km1_index = {s: i for i, s in enumerate(km1_simplices)}
        matrix = [[0] * len(k_simplices) for _ in km1_simplices]
        for j, sigma in enumerate(k_simplices):
            for i, vertex in enumerate(sorted(sigma.vertices)):
                
                face = Simplex(frozenset(sigma.vertices - {vertex}))
                if face in km1_index:
                    matrix[km1_index[face]][j] = (-1) ** i
        return matrix

    def betti_number(self, k: int) -> int:
        """Compute the k-th Betti number β_k = dim(ker ∂_k) - dim(im ∂_(k+1)).

        β_0 = number of connected components
        β_1 = number of independent 1-dim holes (loops)
        β_2 = number of independent 2-dim voids
        """
        
        if k > self.dimension + 1: return 0
        n_k = self.count_simplices(k)
        rank_k = _matrix_rank(self.boundary_matrix(k))
        rank_kp1 = _matrix_rank(self.boundary_matrix(k + 1))
        return n_k - rank_k - rank_kp1

    def betti_numbers(self) -> List[int]:
        """All Betti numbers up to dimension+1."""
        return [self.betti_number(k) for k in range(self.dimension + 2)]

    def euler_characteristic(self) -> int:
        """χ = Σ (-1)^k n_k = Σ (-1)^k β_k (Euler-Poincaré formula)."""
        return sum(((-1) ** k) * self.count_simplices(k)
                   for k in range(self.dimension + 1))


def _matrix_rank(matrix: List[List[int]]) -> int:
    """Compute rank of a matrix over Q (or R) using integer Gauss-Jordan.

    Boundary matrices have small integer entries (0, ±1), so integer
    arithmetic is exact.
    """
    if not matrix or not matrix[0]:
        return 0
    m, n = len(matrix), len(matrix[0])
    A = [list(row) for row in matrix]
    rank = 0
    for col in range(n):
        pivot = None
        for row in range(rank, m):
            if A[row][col] != 0:
                pivot = row
                break
        if pivot is None:
            continue
        A[rank], A[pivot] = A[pivot], A[rank]
        pv = A[rank][col]
        for j in range(col, n):
            A[rank][j] //= pv
        for row in range(m):
            if row == rank:
                continue
            factor = A[row][col]
            if factor == 0:
                continue
            for j in range(col, n):
                A[row][j] -= factor * A[rank][j]
        rank += 1
        if rank == m:
            break
    return rank