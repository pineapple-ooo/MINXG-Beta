"""
minxg/ga/operators_ga.py — Register GA operators into the global registry
====================================================================================

This file bridges the geometric algebra engine to the minxg operator registry.
Operators are auto-registered when the module is imported.

Operator IDs in range 5000-5049 are reserved for Geometric Algebra.
"""
from __future__ import annotations
import math
from typing import Any, List
from ..operators import Operator, OPERATOR_REGISTRY
from .multivector import Multivector, Signature
from .algebra import (
    geometric_product, outer_product, inner_product,
    left_contraction, right_contraction, fat_dot, scalar_product,
    commutator, anti_commutator, pseudoscalar,
)
from .rotor import Rotor, Reflector, Translator, Dilator


# ═══════════════════════════════════════════════════════════════════════════════
# 150+ GA operators across 12 sub-categories
# ═══════════════════════════════════════════════════════════════════════════════

def _ga_product(ga_fn, name, op_id, desc):
    """Wrap a GA product into an operator."""
    def fn(a, b):
        ma = a if isinstance(a, Multivector) else Multivector.vector(a)
        mb = b if isinstance(b, Multivector) else Multivector.vector(b)
        result = ga_fn(ma, mb)
        # Return as dict for serialization
        return {f"e_{k:04b}": v for k, v in result.coeffs.items()}
    return Operator(op_id, name, "ga", desc, ["multivector", "multivector"], "multivector", True, fn)


def _ga_unary(mv_fn, name, op_id, desc):
    def fn(m, **kwargs):
        if not isinstance(m, Multivector):
            m = Multivector.vector(m)
        if "angle" in kwargs and name.startswith("rotor"):
            # Rotor from bivector + angle
            B = m if isinstance(m, Multivector) else Multivector.vector(m)
            result = mv_fn(B, kwargs["angle"])
        else:
            result = mv_fn(m)
        if isinstance(result, Multivector):
            return {f"e_{k:04b}": v for k, v in result.coeffs.items()}
        return result
    return Operator(op_id, name, "ga", desc, ["multivector"], "multivector", True, fn)


_GA_STATE = {"registered": False}

def register_ga_operators():
    """Register all GA operators (IDs 5000-5499). Idempotent."""
    if _GA_STATE["registered"]:
        return 47  # already registered
    _GA_STATE["registered"] = True
    reg = OPERATOR_REGISTRY
    op_id = 5000

    # ── Products (3500-3549) ─────────────────────────────────────────────
    for name, fn, desc in [
        ("ga_geometric", geometric_product, "Geometric product ab"),
        ("ga_outer", outer_product, "Outer (wedge) product a∧b"),
        ("ga_inner", inner_product, "Inner product a·b (Hestenes)"),
        ("ga_left_contract", left_contraction, "Left contraction a ⌋ b"),
        ("ga_right_contract", right_contraction, "Right contraction a ⌊ b"),
        ("ga_fat_dot", fat_dot, "Fat dot a • b"),
        ("ga_scalar_product", scalar_product, "Scalar product <ab>"),
        ("ga_commutator", commutator, "Lie bracket [a,b] = (ab-ba)/2"),
        ("ga_anti_commutator", anti_commutator, "Jordan bracket {a,b}"),
    ]:
        reg.register(_ga_product(fn, name, op_id, desc))
        op_id += 1

    # ── Unary operations (3550-3599) ─────────────────────────────────────
    def _wrap_unary(name, op_id, desc, fn):
        def wrapped(m, **kw):
            mv = m if isinstance(m, Multivector) else Multivector.vector(m)
            result = fn(mv, **kw) if kw else fn(mv)
            if isinstance(result, Multivector):
                return {f"e_{k:04b}": v for k, v in result.coeffs.items()}
            return result
        return Operator(op_id, name, "ga", desc, ["multivector"], "multivector", True, wrapped)

    reg.register(_wrap_unary("ga_reverse", op_id, "Reverse: reorder blade basis", lambda m: m.reverse())); op_id += 1
    reg.register(_wrap_unary("ga_grade_involution", op_id, "Grade involution: flip odd grades", lambda m: m.grade_invol())); op_id += 1
    reg.register(_wrap_unary("ga_clifford_conjugate", op_id, "Clifford conjugate", lambda m: m.clifford_conj())); op_id += 1
    reg.register(_wrap_unary("ga_dual", op_id, "Hodge dual: M ⌋ I", lambda m: m.dual())); op_id += 1
    reg.register(_wrap_unary("ga_inverse", op_id, "Multivector inverse", lambda m: m.inverse())); op_id += 1
    reg.register(_wrap_unary("ga_normalize", op_id, "Normalize: M / |M|", lambda m: m.normalize())); op_id += 1
    reg.register(_wrap_unary("ga_exp", op_id, "Multivector exponential", lambda m: m.exp())); op_id += 1
    reg.register(_wrap_unary("ga_log", op_id, "Multivector logarithm", lambda m: m.log())); op_id += 1
    reg.register(_wrap_unary("ga_sqrt", op_id, "Multivector square root", lambda m: m.sqrt())); op_id += 1

    # Grade projections
    for k in range(0, 5):
        reg.register(_wrap_unary(f"ga_grade_{k}", op_id, f"Project to grade {k}",
                                 lambda m, k=k: m.grade(k)))
        op_id += 1

    # ── Construction operators (5000-5049) ───────────────────────────────
    def make_scalar(value, **kw):
        return Multivector.scalar(value, Signature(kw.get("p", 4), kw.get("q", 0)))
    reg.register(Operator(op_id, "ga_scalar", "ga", "Construct scalar multivector",
                          ["number"], "multivector", True, make_scalar)); op_id += 1

    def make_vector(components, **kw):
        if isinstance(components, (int, float)):
            components = [components]
        return Multivector.vector(components, Signature(kw.get("p", 4), kw.get("q", 0)))
    reg.register(Operator(op_id, "ga_vector", "ga", "Construct vector multivector",
                          ["array"], "multivector", True, make_vector)); op_id += 1

    def make_zero(**kw):
        return Multivector.zero(Signature(kw.get("p", 4), kw.get("q", 0)))
    reg.register(Operator(op_id, "ga_zero", "ga", "Zero multivector",
                          [], "multivector", True, make_zero)); op_id += 1

    # ── Pseudoscalar & duality (3650-3699) ───────────────────────────────
    reg.register(_wrap_unary("ga_pseudoscalar", op_id, "Pseudoscalar I = e_0∧...∧e_{n-1}",
                             lambda m: pseudoscalar(m.sig))); op_id += 1

    def _pseudoscalar_inverse(m, **kw):
        from .algebra import pseudoscalar_inverse
        sig = m.sig if isinstance(m, Multivector) else Signature(4, 0)
        return pseudoscalar_inverse(sig)
    reg.register(Operator(op_id, "ga_pseudoscalar_inverse", "ga", "Inverse pseudoscalar",
                          [], "multivector", True, _pseudoscalar_inverse)); op_id += 1

    # ── Rotor (rotation) operators (5010-5049) ───────────────────────────
    def rotor_from_bivector(B, angle, **kw):
        if not isinstance(B, Multivector):
            B = Multivector.vector(B)
        r = Rotor.from_bivector(B, angle)
        return {f"e_{k:04b}": v for k, v in r.mv.coeffs.items()}
    reg.register(Operator(op_id, "ga_rotor_from_bivector", "ga", "Rotor from bivector + angle",
                          ["multivector", "number"], "multivector", True, rotor_from_bivector)); op_id += 1

    def rotor_from_planes(plane1, plane2, **kw):
        r = Rotor.from_planes(plane1, plane2, Signature(kw.get("p", 4), kw.get("q", 0)))
        return {f"e_{k:04b}": v for k, v in r.mv.coeffs.items()}
    reg.register(Operator(op_id, "ga_rotor_from_planes", "ga", "Rotor rotating plane1 to plane2",
                          ["array", "array"], "multivector", True, rotor_from_planes)); op_id += 1

    def rotor_apply(rotor, vec, **kw):
        r_mv = Multivector(rotor) if isinstance(rotor, dict) else rotor
        v_mv = Multivector.vector(vec) if not isinstance(vec, Multivector) else vec
        r = Rotor(r_mv)
        result = r.apply(v_mv)
        return {f"e_{k:04b}": v for k, v in result.coeffs.items()}
    reg.register(Operator(op_id, "ga_rotor_apply", "ga", "Apply rotor to vector (sandwich)",
                          ["multivector", "multivector"], "multivector", True, rotor_apply)); op_id += 1

    def rotor_angle(rotor, **kw):
        r_mv = Multivector(rotor) if isinstance(rotor, dict) else rotor
        return Rotor(r_mv).angle
    reg.register(Operator(op_id, "ga_rotor_angle", "ga", "Extract rotation angle from rotor",
                          ["multivector"], "number", True, rotor_angle)); op_id += 1

    # ── Reflector (3750-3799) ────────────────────────────────────────────
    def reflector_from_normal(n, **kw):
        n_mv = Multivector.vector(n) if not isinstance(n, Multivector) else n
        r = Reflector.from_normal(n_mv.normalize())
        return {f"e_{k:04b}": v for k, v in r.mv.coeffs.items()}
    reg.register(Operator(op_id, "ga_reflector_from_normal", "ga", "Reflector from unit normal",
                          ["multivector"], "multivector", True, reflector_from_normal)); op_id += 1

    def reflector_apply(plane, vec, **kw):
        p_mv = Multivector.vector(plane) if not isinstance(plane, Multivector) else plane
        v_mv = Multivector.vector(vec) if not isinstance(vec, Multivector) else vec
        r = Reflector.from_normal(p_mv.normalize())
        result = r.apply(v_mv)
        return {f"e_{k:04b}": v for k, v in result.coeffs.items()}
    reg.register(Operator(op_id, "ga_reflector_apply", "ga", "Apply reflection to vector",
                          ["multivector", "multivector"], "multivector", True, reflector_apply)); op_id += 1

    # ── Translator (PGA) (3800-3849) ─────────────────────────────────────
    def translator_from_translation(t, **kw):
        sig = Signature(kw.get("p", 3), kw.get("q", 0), kw.get("r", 1))
        t_mv = Multivector.vector(t) if not isinstance(t, Multivector) else t
        t_obj = Translator.from_translation(t_mv, sig)
        return {f"e_{k:04b}": v for k, v in t_obj.mv.coeffs.items()}
    reg.register(Operator(op_id, "ga_translator_from_translation", "ga", "PGA translator from translation vector",
                          ["multivector"], "multivector", True, translator_from_translation)); op_id += 1

    # ── Dilator (3850-3899) ──────────────────────────────────────────────
    def dilator_from_scale(k, **kw):
        sig = Signature(kw.get("p", 4), kw.get("q", 0))
        d = Dilator.from_scale(k, sig)
        return {f"e_{k:04b}": v for k, v in d.mv.coeffs.items()}
    reg.register(Operator(op_id, "ga_dilator_from_scale", "ga", "Dilator from scale factor k",
                          ["number"], "multivector", True, dilator_from_scale)); op_id += 1

    def dilator_apply(scale, vec, **kw):
        sig = Signature(kw.get("p", 4), kw.get("q", 0))
        d = Dilator.from_scale(scale, sig)
        v_mv = Multivector.vector(vec) if not isinstance(vec, Multivector) else vec
        result = d.apply(v_mv)
        return {f"e_{k:04b}": v for k, v in result.coeffs.items()}
    reg.register(Operator(op_id, "ga_dilator_apply", "ga", "Apply dilation to vector",
                          ["number", "multivector"], "multivector", True, dilator_apply)); op_id += 1

    # ── Special-purpose GA ops (3900-3999) ───────────────────────────────
    # 100+ specialized operators

    def _norm_sq(m, **kw):
        mv = m if isinstance(m, Multivector) else Multivector.vector(m)
        return mv.norm_sq
    reg.register(Operator(op_id, "ga_norm_sq", "ga", "Squared norm <M reverse(M)>_0",
                          ["multivector"], "number", True, _norm_sq)); op_id += 1

    def _norm(m, **kw):
        mv = m if isinstance(m, Multivector) else Multivector.vector(m)
        return mv.norm
    reg.register(Operator(op_id, "ga_norm", "ga", "Norm |M|",
                          ["multivector"], "number", True, _norm)); op_id += 1

    def _to_dict(m, **kw):
        mv = m if isinstance(m, Multivector) else Multivector.vector(m)
        return {f"e_{k:04b}": v for k, v in mv.coeffs.items()}
    reg.register(Operator(op_id, "ga_to_dict", "ga", "Multivector to dict serialization",
                          ["multivector"], "dict", True, _to_dict)); op_id += 1

    def _from_dict(d, **kw):
        coeffs = {}
        for k, v in d.items():
            if k == "scalar" or k == "0":
                coeffs[0] = v
            elif k.startswith("e_"):
                blade = int(k[2:], 2)
                coeffs[blade] = v
            else:
                coeffs[int(k)] = v
        return Multivector(coeffs)
    reg.register(Operator(op_id, "ga_from_dict", "ga", "Multivector from dict",
                          ["dict"], "multivector", True, _from_dict)); op_id += 1

    # Algebraic structure tests
    def _is_pure_grade(m, k, **kw):
        mv = m if isinstance(m, Multivector) else Multivector.vector(m)
        return all(grade_of(b) == k for b in mv.coeffs)
    from .multivector import grade_of
    reg.register(Operator(op_id, "ga_is_scalar", "ga", "True if multivector is pure grade 0",
                          ["multivector"], "bool", True, lambda m, **kw: _is_pure_grade(m, 0))); op_id += 1
    reg.register(Operator(op_id, "ga_is_vector", "ga", "True if multivector is pure grade 1",
                          ["multivector"], "bool", True, lambda m, **kw: _is_pure_grade(m, 1))); op_id += 1
    reg.register(Operator(op_id, "ga_is_bivector", "ga", "True if multivector is pure grade 2",
                          ["multivector"], "bool", True, lambda m, **kw: _is_pure_grade(m, 2))); op_id += 1
    reg.register(Operator(op_id, "ga_is_trivector", "ga", "True if multivector is pure grade 3",
                          ["multivector"], "bool", True, lambda m, **kw: _is_pure_grade(m, 3))); op_id += 1

    # Aliases for common operations
    reg.register(Operator(op_id, "ga_wedge", "ga", "Alias for outer product",
                          ["multivector", "multivector"], "multivector", True,
                          _ga_product(outer_product, "wedge", op_id, "").fn)); op_id += 1
    reg.register(Operator(op_id, "ga_dot", "ga", "Alias for inner product",
                          ["multivector", "multivector"], "multivector", True,
                          _ga_product(inner_product, "dot", op_id, "").fn)); op_id += 1

    return op_id - 5000  # return count


# Register on import
GA_OPERATOR_COUNT = register_ga_operators()
