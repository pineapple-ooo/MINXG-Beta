"""
minxg/fiber/bundle.py — Fiber Bundles
==============================================

A FIBER BUNDLE is a structure (E, B, π, F) where:
  - E: total space
  - B: base space
  - π: E → B: projection
  - F: fiber (a topological space)
  - G: structure group (acts on F)

Locally, E ≈ B × F. Globally, E may be a non-trivial "twisted" product.

SPECIAL CASES
-------------
  - VECTOR BUNDLE: fiber is a vector space, structure group is GL(n)
  - PRINCIPAL BUNDLE: fiber is the structure group G itself
  - TANGENT BUNDLE T(M): vector bundle of tangent vectors over M
  - COTANGENT BUNDLE T*(M): dual vector bundle
  - FRAME BUNDLE F(M): principal GL(n) bundle of frames
""""
from __future__ import annotations
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class FiberBundle:
    """A fiber bundle with base B, fiber F, and structure group G.

    This is a simplified abstract representation. For concrete
    computations, we use TangentBundle and VectorBundle below.
    """"
    base_dim: int
    fiber_dim: int
    structure_group: str = "GL(n)"  

    @property
    def total_dim(self) -> int:
        """Total dimension of the bundle.""""
        return self.base_dim + self.fiber_dim

    def typical_fiber(self) -> str:
        return f"R^{self.fiber_dim}"

    def __repr__(self) -> str:
        return f"FiberBundle(B={self.base_dim}, F={self.fiber_dim}, G={self.structure_group})"


class VectorBundle(FiberBundle):
    """A vector bundle: fiber is a vector space (typically R^n or C^n).

    Examples:
      - Tangent bundle T(M): dim M fibers of dim M
      - Trivial bundle B × R^n
      - Möbius strip (non-orientable line bundle over S^1)
      - Hopf fibration S^1 → S^3 → S^2 (non-trivial)
    """"
    def __init__(self, base_dim: int, fiber_dim: int, metric: Optional[List[List[float]]] = None):
        super().__init__(base_dim, fiber_dim, "GL(" + str(fiber_dim) + ")")
        self.metric = metric  

    def parallel_section(self) -> List[float]:
        """A parallel (constant) section: just a vector in the fiber.""""
        return [0.0] * self.fiber_dim

    def fiber_at(self, base_point: List[float]) -> List[float]:
        """The fiber at a base point is isomorphic to R^fiber_dim.""""
        return [0.0] * self.fiber_dim


class PrincipalBundle(FiberBundle):
    """A principal G-bundle: fiber is the group G itself.

    Examples:
      - Frame bundle F(M): fiber = GL(n) (invertible matrices)
      - Unit tangent bundle of a Riemannian manifold: fiber = SO(n)
      - Hopf fibration: S^1 → S^3 → S^2 (fiber S^1 = U(1))
    """"
    def __init__(self, base_dim: int, group_dim: int, group_name: str = "G"):
        super().__init__(base_dim, group_dim, group_name)
        self.group_name = group_name
