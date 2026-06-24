"""
minxg/ga/algebra.py — Core products of Geometric Algebra
=================================================================

This file implements the five fundamental products of Clifford algebra:

  1. **Geometric product**     ab = a·b + a∧b
  2. **Outer (wedge) product** a∧b  (antisymmetric, generalizes cross product)
  3. **Inner (dot) product**   a·b  (symmetric in Euclidean, but grade-lowering)
  4. **Left contraction**      a ⌋ b  (grade-lowering from a)
  5. **Right contraction**     a ⌊ b  (grade-lowering from b)
  6. **Fat dot**               a • b  (max grade-lowering — symmetric form)
  7. **Scalar product**        <ab>_0  (extracts grade-0 part)
  8. **Commutator**            [a,b] = ab - ba  (Lie algebra structure)
  9. **Anti-commutator**       {a,b} = ab + ba  (Jordan algebra structure)

ALGORITHM
---------
For two basis blades B_a and B_b, the geometric product is:
  B_a * B_b = sign(B_a, B_b) * B_a∪B_b  if disjoint, else 0 (for 0-Clifford)
  where sign is from sorting the concatenated basis vectors into canonical order.

For general multivectors, we sum over all pairs of components. With sparse
storage (k non-zero blades per multivector), this is O(k²) per product,
which is fast for typical AI workloads where k ≤ 8.

The metric enters via the simplification rule:
  e_i * e_i = metric(i)  (which equals +1, -1, or 0)
"""
from __future__ import annotations
import math
from typing import Dict, Tuple
from .multivector import (
    Multivector, Signature,
    grade_of, basis_grade_index, blade_outer, blade_sign,
)




def _blade_product(a_blade: int, a_coeff: float,
                   b_blade: int, b_coeff: float,
                   sig: Signature) -> Tuple[int, float]:
    """Compute the geometric product of two basis blades.

    Returns (result_blade, result_coeff). result_blade = 0 means scalar part.

    Algorithm: 1) count inversions (sign from anticommuting grade-1 basis
    vectors), 2) pair up repeated indices (each pair contributes metric(i)),
    3) collect remaining singletons as a sorted basis blade.
    """
    if a_blade == 0:
        return (b_blade, a_coeff * b_coeff)
    if b_blade == 0:
        return (a_blade, a_coeff * b_coeff)

    a_bits = basis_grade_index(a_blade)
    b_bits = basis_grade_index(b_blade)

    inversions = 0
    for b_bit in b_bits:
        for a_bit in a_bits:
            if a_bit > b_bit:
                inversions += 1
    sign = -1 if inversions % 2 else 1

    counts: Dict[int, int] = {}
    for idx in a_bits + b_bits:
        counts[idx] = counts.get(idx, 0) + 1

    final_blades = []
    final_metric = 1.0
    for idx in sorted(counts.keys()):
        c = counts[idx]
        pairs = c // 2
        leftover = c % 2
        if pairs > 0:
            final_metric *= sig.metric(idx) ** pairs
        for _ in range(leftover):
            final_blades.append(idx)

    final_blade = 0
    for idx in final_blades:
        final_blade |= (1 << idx)

    return (final_blade, a_coeff * b_coeff * sign * final_metric)

    
    
    
    result_blade = 0
    for idx in combined:
        result_blade |= (1 << idx)

    
    metric_factor = 1.0
    
    
    
    
    i = 0
    final_blades = []
    final_metric = 1.0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j] == combined[i]:
            j += 1
        run_length = j - i
        
        pairs = run_length // 2
        leftover = run_length % 2
        final_metric *= sig.metric(combined[i]) ** pairs
        for _ in range(leftover):
            final_blades.append(combined[i])
        i = j

    
    final_blades.sort()
    final_sign = 1
    final_blade = 0
    for idx in final_blades:
        
        final_blade |= (1 << idx)

    return (final_blade, a_coeff * b_coeff * sign * final_metric * final_sign)




def geometric_product(a: Multivector, b: Multivector) -> Multivector:
    """The geometric product ab. The fundamental product of GA.

    Decomposes as: ab = a·b + a∧b (inner + outer).
    """
    if a.sig != b.sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    sig = a.sig
    out: Dict[int, float] = {}
    for ba, ca in a.coeffs.items():
        for bb, cb in b.coeffs.items():
            rb, rc = _blade_product(ba, ca, bb, cb, sig)
            if rc == 0:
                continue
            out[rb] = out.get(rb, 0.0) + rc
    return Multivector(out, sig)


def outer_product(a: Multivector, b: Multivector) -> Multivector:
    """The outer (wedge, exterior) product a∧b.

    The grade of a∧b is grade(a) + grade(b). It's antisymmetric:
        a ∧ b = -b ∧ a
    For basis blades sharing any index, a∧b = 0.
    """
    sig = a.sig
    if b.sig != sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    out: Dict[int, float] = {}
    for ba, ca in a.coeffs.items():
        for bb, cb in b.coeffs.items():
            if ba & bb:
                continue
            rb = ba | bb
            sign = blade_sign(ba, bb)
            if sign == 0:
                continue
            out[rb] = out.get(rb, 0.0) + sign * ca * cb
    return Multivector(out, sig)


def inner_product(a: Multivector, b: Multivector) -> Multivector:
    """The Hestenes inner product (a·b).

    Defined for blades of grades r and s:
        e_A · e_B = 0  if A and B are disjoint (no shared basis)
                  = (e_A∪B' · e_B) e_A∩B  (complicated case)

    For a vector v and r-blade B: v·B = grade projection of vB onto grade r-1.
    """
    
    if a.sig != b.sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    ab = geometric_product(a, b)
    
    
    if not b.coeffs:
        return Multivector.zero(a.sig)
    max_b_grade = max(grade_of(bb) for bb in b.coeffs)
    target = max_b_grade - 1
    return ab.grade(target)


def left_contraction(a: Multivector, b: Multivector) -> Multivector:
    """Left contraction: a ⌋ b. Lowers the grade of a.

    For blades of grades r and s:
        e_A ⌋ e_B = (e_A · e_B) e_A∧e_B'   if e_A ⊆ e_B, else 0
    The grade of the result is s - r.
    """
    if a.sig != b.sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    out: Dict[int, float] = {}
    for ba, ca in a.coeffs.items():
        for bb, cb in b.coeffs.items():
            
            if ba & bb != ba:
                continue
            rb = bb & ~ba
            
            sign = 1
            
            out[rb] = out.get(rb, 0.0) + sign * ca * cb
    return Multivector(out, a.sig)


def right_contraction(a: Multivector, b: Multivector) -> Multivector:
    """Right contraction: a ⌊ b. Lowers the grade of b.

    For blades of grades r and s:
        e_A ⌊ e_B = 0  if e_B ⊄ e_A
                   = (e_A · e_B) e_A∧e_B'  otherwise
    The grade of the result is r - s.
    """
    if a.sig != b.sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    out: Dict[int, float] = {}
    for ba, ca in a.coeffs.items():
        for bb, cb in b.coeffs.items():
            if bb & ba != bb:
                continue
            rb = ba & ~bb
            out[rb] = out.get(rb, 0.0) + ca * cb
    return Multivector(out, a.sig)


def fat_dot(a: Multivector, b: Multivector) -> Multivector:
    """Fat dot: a • b. The symmetric "scalar-extracting" form.

    For blades of grades r, s:
        e_A • e_B = 0  if r != s
                  = (-1)^(r(r-1)/2) (e_A · e_B)  if r = s
    """
    if a.sig != b.sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    out: Dict[int, float] = {}
    for ba, ca in a.coeffs.items():
        for bb, cb in b.coeffs.items():
            ga, gb = grade_of(ba), grade_of(bb)
            if ga != gb:
                continue
            if ba != bb:
                continue
            
            sign = -1 if (ga * (ga - 1) // 2) % 2 else 1
            out[0] = out.get(0, 0.0) + sign * ca * cb
    return Multivector(out, a.sig)


def scalar_product(a: Multivector, b: Multivector) -> float:
    """Extracts the scalar (grade-0) part of a*b."""
    if a.sig != b.sig:
        raise ValueError(f"Signature mismatch: {a.sig} vs {b.sig}")
    return geometric_product(a, b)[0]


def commutator(a: Multivector, b: Multivector) -> Multivector:
    """Lie bracket: [a,b] = (ab - ba) / 2.

    Makes the multivector space a graded Lie algebra. For bivectors,
    this is the standard Lie algebra of the rotation group.
    """
    return (geometric_product(a, b) - geometric_product(b, a)) * 0.5


def anti_commutator(a: Multivector, b: Multivector) -> Multivector:
    """Jordan bracket: {a,b} = (ab + ba) / 2.

    Makes the multivector space a Jordan algebra.
    """
    return (geometric_product(a, b) + geometric_product(b, a)) * 0.5




def pseudoscalar(sig: Signature) -> Multivector:
    """The unit pseudoscalar I = e_0 ∧ e_1 ∧ ... ∧ e_{n-1}.

    I² = (-1)^(r(r-1)/2 + sum of negative-metric basis)
    Used for Hodge dual: M* = M ⌋ I  (or M I⁻¹).
    """
    n = sig.n
    blade = (1 << n) - 1  
    return Multivector({blade: 1.0}, sig)


def pseudoscalar_inverse(sig: Signature) -> Multivector:
    """The inverse of the pseudoscalar, used for right Hodge dual."""
    n = sig.n
    blade = (1 << n) - 1
    I = Multivector({blade: 1.0}, sig)
    return I.inverse()
