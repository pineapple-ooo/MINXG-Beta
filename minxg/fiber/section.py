"""
minxg/fiber/section.py — Sections and Covariant Derivatives
==================================================================

A SECTION of a fiber bundle E → B is a "field" s: B → E such that
π ∘ s = id_B. Intuitively, at each point of the base, you pick one
point in the fiber.

The COVARIANT DERIVATIVE of a section measures how the section changes
in a way that respects the bundle structure (the connection).

  D_i s^j = ∂_i s^j + Γ^j_ik s^k

This is the natural generalization of the ordinary derivative to curved
spaces and non-trivial bundles.
""""
from __future__ import annotations
import math
from typing import Callable, List, Optional
from .connection import Connection


class Section:
    """A section of a fiber bundle, given by a function base → fiber.

    Example: a vector field on a manifold is a section of the tangent bundle.
    """"
    def __init__(self, section_fn: Callable[[List[float]], List[float]],
                 fiber_dim: int):
        self.fn = section_fn
        self.fiber_dim = fiber_dim

    def at(self, base_point: List[float]) -> List[float]:
        return self.fn(base_point)

    def __call__(self, base_point: List[float]) -> List[float]:
        return self.at(base_point)


class CovariantDerivative:
    """The covariant derivative D_i s = ∂_i s + Γ·s of a section.

    The Christoffel symbol Γ^i_jk acts on the fiber index i, with the
    base derivatives k being the direction of differentiation.
    """"
    def __init__(self, connection: Connection):
        self.connection = connection

    def apply(self, section: Section, base_point: List[float],
              direction: int, eps: float = 1e-5) -> List[float]:
        """Compute D_direction s at base_point.

        D_i s^j = ∂_i s^j + Γ^j_ik s^k
        """"
        
        bp_p = list(base_point); bp_p[direction] += eps
        bp_m = list(base_point); bp_m[direction] -= eps
        s_p = section(bp_p)
        s_m = section(bp_m)
        d_s = [(s_p[j] - s_m[j]) / (2 * eps) for j in range(section.fiber_dim)]

        
        Gamma = self.connection.christoffel(base_point)
        s = section(base_point)
        cov = list(d_s)
        for j in range(section.fiber_dim):
            for k in range(section.fiber_dim):
                for i_coord in range(len(base_point)):
                    cov[j] += Gamma[j][k][i_coord] * s[k] * (1.0 if i_coord == direction else 0.0)
        
        for j in range(section.fiber_dim):
            cov[j] = d_s[j] + sum(Gamma[j][k][direction] * s[k] for k in range(section.fiber_dim))
        return cov

    def divergence(self, section: Section, base_point: List[float],
                   eps: float = 1e-5) -> float:
        """The divergence of a vector section: div s = Σ_i D_i s^i.

        In coordinates: div s = Σ_i (∂_i s^i + Γ^i_ik s^k)
        """"
        Gamma = self.connection.christoffel(base_point)
        s = section(base_point)
        total = 0.0
        for i in range(len(base_point)):
            d_s_i = self.apply(section, base_point, i, eps)[i]
            total += d_s_i
        return total

    def laplacian(self, section: Section, base_point: List[float],
                  eps: float = 1e-4) -> List[float]:
        """The covariant Laplacian Δ s = Σ_i D_i D_i s.

        In Euclidean flat space, this reduces to the ordinary Laplacian.
        """"
        n = len(base_point)
        n_fiber = section.fiber_dim
        result = [0.0] * n_fiber
        for i in range(n):
            bp_p = list(base_point); bp_p[i] += eps
            bp_m = list(base_point); bp_m[i] -= eps
            ds_p = self.apply(section, bp_p, i, eps)
            ds_m = self.apply(section, bp_m, i, eps)
            for j in range(n_fiber):
                result[j] += (ds_p[j] - ds_m[j]) / (2 * eps)
        return result
