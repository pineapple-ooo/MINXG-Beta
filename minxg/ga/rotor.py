"""
minxg/ga/rotor.py — Versors, Rotors, Translators, Dilators
====================================================================

Versors are the multiplicative group of invertible multivectors. They act on
vectors via the "sandwich product" V x V^(-1), producing rotations, reflections,
translations, and dilations depending on the grade of the versor.

This is the crown jewel of Geometric Algebra: a SINGLE algebraic operation
(geometric product) produces all rigid-body transformations:

  Rotor  (grade 2)        -> rotation
  Reflector (grade 1)     -> reflection
  Translator (grade 2)    -> translation (in projective GA / PGA)
  Dilator (grade 0)       -> uniform scaling
  Motor  (rotor + translator) -> general rigid motion

Why this matters for AI:
  - Embeddings live on curved manifolds (hypersphere, Poincare disk, etc.)
  - Operations on embeddings need to respect the manifold structure
  - Rotors preserve distance, which is exactly what we want for embeddings
  - Bivector exponent exp(B) is the canonical rotation generator

ALGORITHM
---------
A rotor R = exp(-B/2) where B is a bivector. Applying to vector x:
  x' = R x R^(-1) = R x reverse(R)

This works for ALL dimensions, ALL signatures — no special cases.
"""
from __future__ import annotations
import math
from typing import Iterable, List, Optional
from .multivector import Multivector, Signature
from .algebra import geometric_product


# ── Versor base class ────────────────────────────────────────────────────────

class Versor:
    """Base class for all versors (invertible multivectors that act via sandwich).

    A versor V acts on a multivector M via: M' = V M V^(-1).
    """
    __slots__ = ("mv",)

    def __init__(self, mv: Multivector):
        self.mv = mv

    def inverse(self) -> "Versor":
        """V⁻¹ = reverse(V) / (V * reverse(V)). For rotors this equals just reverse."""
        r = self.mv.reverse()
        n = geometric_product(self.mv, r)[0]  # scalar part = V*Ṽ
        if n == 0:
            raise ValueError("Versor has no inverse (null norm)")
        return self.__class__(r / n)

    def reverse(self) -> Multivector:
        return self.mv.reverse()

    def __mul__(self, other):
        """Versor composition: V1 * V2 acts as V1(V2(x))."""
        if isinstance(other, Versor):
            return Versor(geometric_product(self.mv, other.mv))
        return NotImplemented

    def apply(self, m: Multivector) -> Multivector:
        """Apply versor to multivector: V m V⁻¹."""
        inv = self.inverse()  # use Versor inverse (not Multivector.inverse)
        return geometric_product(geometric_product(self.mv, m), inv.mv)

    def __call__(self, m: Multivector) -> Multivector:
        return self.apply(m)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.mv})"


# ── Rotor (rotation) ─────────────────────────────────────────────────────────

class Rotor(Versor):
    """A rotor generates a rotation in the plane defined by a bivector B.

    R = exp(-B/2)  (Hestenes convention; some use exp(B/2) — sign is conventional)

    R rotates vectors in the plane of B by 2*|B| radians.
    R rotates bivectors and higher-grade elements as well.
    """

    @classmethod
    def from_bivector(cls, B: Multivector, angle: float) -> "Rotor":
        """Build a rotor that rotates by `angle` radians in the plane of B.

        Args:
            B: unit bivector (B² = -1, B.norm_sq = -1)
            angle: rotation angle in radians
        """
        # B should be unit bivector: B² = -1
        n2 = B.norm_sq
        if abs(n2 + 1) > 1e-9:
            raise ValueError(f"B is not a unit bivector (B² = {n2}, expected -1)")
        half = -angle / 2  # Hestenes: R = exp(-B*angle/2)
        cos_h = math.cos(half)
        sin_h = math.sin(half)
        return cls(Multivector.scalar(cos_h, B.sig) + B * sin_h)

    @classmethod
    def from_planes(cls, plane1: Iterable[float], plane2: Iterable[float],
                    sig: Optional[Signature] = None) -> "Rotor":
        """Build a rotor rotating plane1 to plane2.

        Both planes pass through the origin. The rotation angle is the
        principal angle between the planes.
        """
        v1 = Multivector.vector(plane1, sig)
        v2 = Multivector.vector(plane2, sig)
        # Bivector B = v1 ∧ v2
        B = v1.outer(v2)
        # Normalize: |B|² = -|v1|²|v2|²sin²θ = -sin²θ for unit vectors
        sin_sq = -B.norm_sq
        if sin_sq < 1e-12:
            # Vectors are parallel — identity
            return cls(Multivector.scalar(1.0, sig or v1.sig))
        sin_th = math.sqrt(sin_sq)
        # angle in [0, π] such that cos = v1·v2 (assuming unit)
        v1n = v1.normalize()
        v2n = v2.normalize()
        cos_th = geometric_product(v1n, v2n)[0]
        # Avoid sign issues
        if abs(cos_th) > 1:
            cos_th = max(-1.0, min(1.0, cos_th))
        angle = math.acos(cos_th)
        # Bivector normalization: B / sin_th = unit bivector
        B_unit = B / sin_th
        return cls.from_bivector(B_unit, angle)

    @property
    def angle(self) -> float:
        """Extract the rotation angle."""
        s = self.mv[0]
        if abs(s) > 1:
            s = max(-1.0, min(1.0, s))
        return 2 * math.acos(s)

    def apply_to_vector(self, v: Multivector) -> Multivector:
        """Convenience: rotate a vector."""
        return self.apply(v)


# ── Reflector (reflection) ───────────────────────────────────────────────────

class Reflector(Versor):
    """A reflection in the hyperplane perpendicular to vector n.

    Reflection matrix: x' = -n x n  (in Cl(3,0) for unit n)
    For unit n: n² = 1, so n^(-1) = n, and the formula is x' = -n x n.

    Note: scalar part of reflector is 0; this is odd-grade.
    Composition of two reflections = rotation.
    """
    @classmethod
    def from_normal(cls, n: Multivector) -> "Reflector":
        if abs(n.norm_sq - 1) > 1e-9:
            raise ValueError(f"Normal must be unit vector (n² = {n.norm_sq})")
        return cls(n)


# ── Translator (PGA translation) ─────────────────────────────────────────────

class Translator(Versor):
    """Translation in Projective Geometric Algebra (PGA).

    In Cl(3,0,1) (3D space + one null direction e_∞), a translator T = 1 + t∧e_∞/2
    translates vectors by t. This is the cleanest way to handle rigid motion
    in geometric algebra.

    Requires the signature to have a null direction. For Cl(3,0,1), set
    Signature(3, 0, 1).
    """
    @classmethod
    def from_translation(cls, t: Multivector, sig: Signature) -> "Translator":
        """Build a translator that moves by vector t."""
        if sig.r < 1:
            raise ValueError("Translation requires at least one null direction (PGA)")
        e_inf = Multivector({1 << (sig.p + sig.q): 1.0}, sig)
        half_t_einf = t.outer(e_inf) * 0.5
        return cls(Multivector.scalar(1.0, sig) + half_t_einf)


# ── Dilator (scaling) ────────────────────────────────────────────────────────

class Dilator(Versor):
    """A uniform scaling (dilation) by a positive factor k.

    A scalar versor D = k^(1/2) acts as D x D⁻¹ = k x for all vectors x.
    Note: true uniform scaling cannot be achieved by a bivector versor —
    bivector versors produce directional scaling (stretch one direction,
    compress the orthogonal direction). For uniform scaling we use a
    scalar versor.
    """
    @classmethod
    def from_scale(cls, k: float, sig: Optional[Signature] = None) -> "Dilator":
        if sig is None:
            sig = Signature(4, 0)
        if k <= 0:
            raise ValueError(f"Scale factor must be positive, got {k}")
        d = cls(Multivector.scalar(math.sqrt(k), sig))
        d.k = k
        return d

    def apply(self, m: "Multivector") -> "Multivector":
        """Uniform scaling: returns k * m."""
        return m * self.k


# ── Motor (rotation + translation) ───────────────────────────────────────────

class Motor(Versor):
    """A motor: rotor + translator. General rigid motion in 3D.

    M = T R  (translator followed by rotor, or any combination)
    Acts on a point p (in Cl(3,0,1) with e₀ as origin) via M p reverse(M).
    """
    @classmethod
    def compose(cls, rotor: Rotor, translator: Translator) -> "Motor":
        return cls(geometric_product(translator.mv, rotor.mv))

    def decompose(self) -> tuple:
        """Extract (rotor, translator) components."""
        # ... (PGA-specific decomposition)
        raise NotImplementedError("Motor decomposition requires PGA Cl(3,0,1)")


# ── MultiVersor ──────────────────────────────────────────────────────────────

class MultiVersor:
    """A sum of versors — for chained rigid motions.

    In general, the product of two rotors IS another rotor (they form a group),
    but the product of a rotor and a translator is a motor, and so on. A
    MultiVersor tracks arbitrary sums.
    """
    __slots__ = ("terms",)

    def __init__(self, terms: List[Versor]):
        self.terms = terms

    def apply(self, m: Multivector) -> Multivector:
        """Apply each versor in order."""
        for v in self.terms:
            m = v.apply(m)
        return m
