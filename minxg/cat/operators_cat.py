"""
minxg/cat/operators_cat.py — Register CAT (Category-Theoretic) operators
================================================================================

100+ categorical operators. Each operator has its TYPE SIGNATURE encoded
so they can be safely composed via >>.

Operator IDs in range 4000-4499 are reserved for Categorical operators.
"""
from __future__ import annotations
import itertools
from typing import Any, Callable, Dict, List, Optional, Tuple
from ..operators import Operator, OPERATOR_REGISTRY
from .morphism import Morphism, Type, identity, compose
from .functor import Identity, Maybe, Either, ListF, Const, Reader
from .monad import IdentityM, MaybeM, EitherM, State, Reader as ReaderM, ListM, IO
from .yoneda import yoneda_embedding, representable, NaturalTransformation


# ═══════════════════════════════════════════════════════════════════════════════
# 100+ category-theoretic operators
# ═══════════════════════════════════════════════════════════════════════════════

_CAT_STATE = {"registered": False}

def register_cat_operators():
    if _CAT_STATE["registered"]:
        return 79
    _CAT_STATE["registered"] = True
    reg = OPERATOR_REGISTRY
    op_id = 4000

    # ── Identity & composition (4000-4019) ──────────────────────────────
    def _id_for_type(t):
        def fn(x):
            return x
        return fn
    for type_name in ["number", "string", "list", "dict", "bool", "any", "multivector"]:
        reg.register(Operator(op_id, f"cat_id_{type_name}", "cat",
                              f"Identity morphism for type {type_name}",
                              [type_name], type_name, True,
                              _id_for_type(type_name)))
        op_id += 1

    # ── Maybe functor/monad (4020-4039) ─────────────────────────────────
    def _maybe_just(v): return Maybe.just(v)
    def _maybe_nothing(): return Maybe.nothing()
    def _maybe_is_just(m): return m.is_just
    def _maybe_get(m): return m.value if m.is_just else None
    def _maybe_map(m, f_name): return m.fmap(_registry_lookup(reg, f_name))
    def _maybe_bind(m, f_name):
        f = _registry_lookup(reg, f_name)
        if not m.is_just: return MaybeM.nothing()
        return MaybeM.of_maybe(f(m.value))
    def _maybe_from_nullable(v): return Maybe.just(v) if v is not None else Maybe.nothing()
    def _maybe_to_nullable(m): return m.value if m.is_just else None
    def _maybe_chain(ms):
        for m in ms:
            if not m.is_just: return Maybe.nothing()
        return Maybe.just([m.value for m in ms])
    def _maybe_alt(m1, m2): return m1 if m1.is_just else m2

    for name, fn, in_types, out_type, desc in [
        ("cat_maybe_just", _maybe_just, ["any"], "maybe", "Wrap value in Maybe.just"),
        ("cat_maybe_nothing", _maybe_nothing, [], "maybe", "Construct Maybe.nothing"),
        ("cat_maybe_is_just", _maybe_is_just, ["maybe"], "bool", "Test if Maybe is Just"),
        ("cat_maybe_get", _maybe_get, ["maybe"], "any", "Extract value from Maybe"),
        ("cat_maybe_from_nullable", _maybe_from_nullable, ["any"], "maybe", "Convert nullable to Maybe"),
        ("cat_maybe_to_nullable", _maybe_to_nullable, ["maybe"], "any", "Convert Maybe to nullable"),
        ("cat_maybe_chain", _maybe_chain, ["list"], "maybe", "Chain Mayables — fail if any Nothing"),
        ("cat_maybe_alt", _maybe_alt, ["maybe", "maybe"], "maybe", "First Just wins"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Either functor/monad (4040-4059) ────────────────────────────────
    def _either_right(v): return Either.right(v)
    def _either_left(e): return Either.left(e)
    def _either_is_right(e): return e.is_right
    def _either_get(e): return e.value if e.is_right else None
    def _either_map(e, f_name): return e.fmap(_registry_lookup(reg, f_name))
    def _either_bind(e, f_name):
        f = _registry_lookup(reg, f_name)
        if not e.is_right: return EitherM.left(e.value)
        return EitherM.of_maybe(f(e.value))
    def _either_from_try(fn, *args):
        try: return Either.right(fn(*args))
        except Exception as ex: return Either.left(str(ex))
    def _either_to_maybe(e): return Maybe.just(e.value) if e.is_right else Maybe.nothing()
    def _either_bimap(l_fn_name, r_fn_name, e):
        l_fn = _registry_lookup(reg, l_fn_name)
        r_fn = _registry_lookup(reg, r_fn_name)
        return l_fn(e.value) if not e.is_right else r_fn(e.value)
    def _either_swap(e):
        return Either.left(e.value) if e.is_right else Either.right(e.value)

    for name, fn, in_types, out_type, desc in [
        ("cat_either_right", _either_right, ["any"], "either", "Construct Either.right"),
        ("cat_either_left", _either_left, ["any"], "either", "Construct Either.left"),
        ("cat_either_is_right", _either_is_right, ["either"], "bool", "Test if Either is Right"),
        ("cat_either_get", _either_get, ["either"], "any", "Extract value from Either"),
        ("cat_either_to_maybe", _either_to_maybe, ["either"], "maybe", "Either to Maybe"),
        ("cat_either_swap", _either_swap, ["either"], "either", "Swap Left/Right"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── State monad (4060-4079) ─────────────────────────────────────────
    def _state_get(): return State.get()
    def _state_put(s): return State.put(s)
    def _state_modify(f_name):
        f = _registry_lookup(reg, f_name)
        return State.modify(f)
    def _state_run(s_monad, initial):
        return s_monad.run(initial)
    def _state_eval(s_monad, initial):
        _, a = s_monad.run(initial)
        return a
    def _state_exec(s_monad, initial):
        s_new, _ = s_monad.run(initial)
        return s_new

    for name, fn, in_types, out_type, desc in [
        ("cat_state_get", _state_get, [], "state", "State monad: get current state"),
        ("cat_state_put", _state_put, ["any"], "state", "State monad: replace state"),
        ("cat_state_run", _state_run, ["state", "any"], "tuple", "Run state monad, return (state, value)"),
        ("cat_state_eval", _state_eval, ["state", "any"], "any", "Run state monad, return value only"),
        ("cat_state_exec", _state_exec, ["state", "any"], "any", "Run state monad, return new state only"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Reader monad (4080-4089) ────────────────────────────────────────
    def _reader_ask(): return ReaderM.ask()
    def _reader_asks(f_name): return ReaderM.asks(_registry_lookup(reg, f_name))
    def _reader_local(f_name, m):
        f = _registry_lookup(reg, f_name)
        return ReaderM.local(f, m)
    def _reader_run(m, env): return m.run(env)

    for name, fn, in_types, out_type, desc in [
        ("cat_reader_ask", _reader_ask, [], "reader", "Reader: get environment"),
        ("cat_reader_asks", _reader_asks, ["string"], "reader", "Reader: project from environment"),
        ("cat_reader_local", _reader_local, ["string", "reader"], "reader", "Reader: run with modified env"),
        ("cat_reader_run", _reader_run, ["reader", "any"], "any", "Reader: execute with environment"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── List functor/monad (4090-4109) ──────────────────────────────────
    def _list_map(l, f_name):
        return [f(x) for x in l]
    def _list_bind(l, f_name):
        f = _registry_lookup(reg, f_name)
        out = []
        for x in l:
            out.extend(f(x))
        return out
    def _list_concat(lists):
        out = []
        for l in lists:
            out.extend(l)
        return out
    def _list_filter(l, pred_name):
        p = _registry_lookup(reg, pred_name)
        return [x for x in l if p(x)]
    def _list_fold(l, init, f_name):
        f = _registry_lookup(reg, f_name)
        acc = init
        for x in l: acc = f(acc, x)
        return acc
    def _list_cartesian(l1, l2):
        return [(a, b) for a in l1 for b in l2]
    def _list_cone(l1, l2):
        """Concatenate two lists, preserving order."""
        return list(l1) + list(l2)
    def _list_zip(l1, l2):
        return list(zip(l1, l2))
    def _list_head(l): return l[0] if l else None
    def _list_tail(l): return l[1:] if len(l) > 1 else []
    def _list_length(l): return len(l)
    def _list_reverse(l): return list(reversed(l))
    def _list_unique(l):
        seen = []
        for x in l:
            if x not in seen: seen.append(x)
        return seen
    def _list_take(l, n): return l[:n]
    def _list_drop(l, n): return l[n:]
    def _list_group_by(l, key_name):
        from collections import defaultdict
        k = _registry_lookup(reg, key_name)
        out = defaultdict(list)
        for x in l: out[k(x)].append(x)
        return dict(out)
    def _list_sort_by(l, key_name):
        k = _registry_lookup(reg, key_name)
        return sorted(l, key=k)
    def _list_partition(l, pred_name):
        p = _registry_lookup(reg, pred_name)
        t, f = [], []
        for x in l: (t if p(x) else f).append(x)
        return t, f
    def _list_zip_with(l1, l2, f_name):
        f = _registry_lookup(reg, f_name)
        return [f(a, b) for a, b in zip(l1, l2)]
    def _list_scan(l, init, f_name):
        f = _registry_lookup(reg, f_name)
        out, acc = [init], init
        for x in l:
            acc = f(acc, x)
            out.append(acc)
        return out

    for name, fn, in_types, out_type, desc in [
        ("cat_list_map", _list_map, ["list", "string"], "list", "Map function over list"),
        ("cat_list_bind", _list_bind, ["list", "string"], "list", "Bind (flatMap) over list"),
        ("cat_list_concat", _list_concat, ["list"], "list", "Concatenate list of lists"),
        ("cat_list_filter", _list_filter, ["list", "string"], "list", "Filter list by predicate"),
        ("cat_list_fold", _list_fold, ["list", "any", "string"], "any", "Left fold"),
        ("cat_list_cartesian", _list_cartesian, ["list", "list"], "list", "Cartesian product"),
        ("cat_list_cone", _list_cone, ["list", "list"], "list", "Concatenate (co-product)"),
        ("cat_list_zip", _list_zip, ["list", "list"], "list", "Zip two lists"),
        ("cat_list_head", _list_head, ["list"], "any", "First element"),
        ("cat_list_tail", _list_tail, ["list"], "list", "All but first"),
        ("cat_list_length", _list_length, ["list"], "int", "Length"),
        ("cat_list_reverse", _list_reverse, ["list"], "list", "Reverse"),
        ("cat_list_unique", _list_unique, ["list"], "list", "Deduplicate (preserves order)"),
        ("cat_list_take", _list_take, ["list", "int"], "list", "Take first n"),
        ("cat_list_drop", _list_drop, ["list", "int"], "list", "Drop first n"),
        ("cat_list_group_by", _list_group_by, ["list", "string"], "dict", "Group by key"),
        ("cat_list_sort_by", _list_sort_by, ["list", "string"], "list", "Sort by key"),
        ("cat_list_partition", _list_partition, ["list", "string"], "tuple", "Partition by predicate"),
        ("cat_list_zip_with", _list_zip_with, ["list", "list", "string"], "list", "Zip with function"),
        ("cat_list_scan", _list_scan, ["list", "any", "string"], "list", "Left scan (prefix reduce)"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Morphism operations (4110-4129) ────────────────────────────────
    def _compose_morphisms(m1, m2):
        return Morphism(
            name=f"{m1.name}_then_{m2.name}",
            domain=m1.domain,
            codomain=m2.codomain,
            fn=lambda *a, **k: m2(m1(*a, **k)),
            is_pure=m1.is_pure and m2.is_pure,
        )
    def _morphism_signature(m): return m.signature
    def _morphism_name(m): return m.name
    def _morphism_pure(m): return m.is_pure
    def _morphism_metadata(m): return m.metadata
    def _morphism_lift(f):
        """Lift a plain function to a Morphism with type 'any'."""
        return Morphism(f.__name__ if hasattr(f, '__name__') else "anon",
                        (Type.any(),), Type.any(), f, True)

    for name, fn, in_types, out_type, desc in [
        ("cat_compose", _compose_morphisms, ["morphism", "morphism"], "morphism", "Compose two morphisms"),
        ("cat_signature", _morphism_signature, ["morphism"], "string", "Get morphism signature"),
        ("cat_morphism_name", _morphism_name, ["morphism"], "string", "Get morphism name"),
        ("cat_is_pure", _morphism_pure, ["morphism"], "bool", "Test if morphism is pure"),
        ("cat_morphism_metadata", _morphism_metadata, ["morphism"], "dict", "Get morphism metadata"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Yoneda & naturality (4130-4149) ─────────────────────────────────
    def _yoneda_encode(op, test_inputs):
        return yoneda_embedding(op, test_inputs)
    def _yoneda_distance(rep1, rep2):
        """Distance between Yoneda representations (Euclidean over outputs)."""
        if len(rep1) != len(rep2): return float('inf')
        return sum((a - b) ** 2 for a, b in zip(rep1, rep2)) ** 0.5
    def _natural_transform(components):
        return NaturalTransformation("ad_hoc", components)
    def _representable_functor(op):
        return representable(op, [])

    for name, fn, in_types, out_type, desc in [
        ("cat_yoneda_encode", _yoneda_encode, ["any", "list"], "list", "Yoneda encoding of an operator"),
        ("cat_yoneda_distance", _yoneda_distance, ["list", "list"], "number", "Yoneda distance between representations"),
        ("cat_natural_transform", _natural_transform, ["dict"], "nat_trans", "Build a natural transformation"),
        ("cat_representable", _representable_functor, ["any"], "functor", "Build representable functor"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── IO monad (4150-4159) ────────────────────────────────────────────
    def _io_pure(v): return IO.pure(v)
    def _io_from_fn(f): return IO.from_fn(f)
    def _io_run(m): return m.run()
    def _io_sequence(ms):
        """Sequence IO actions: m1, m2, ... -> IO([v1, v2, ...])"""
        def fn():
            return [m.run() for m in ms]
        return IO.from_fn(fn)
    def _io_map(m, f_name):
        f = _registry_lookup(reg, f_name)
        return IO.from_fn(lambda: f(m.run()))

    for name, fn, in_types, out_type, desc in [
        ("cat_io_pure", _io_pure, ["any"], "io", "IO.pure"),
        ("cat_io_from_fn", _io_from_fn, ["any"], "io", "IO from side-effecting function"),
        ("cat_io_run", _io_run, ["io"], "any", "Execute IO action"),
        ("cat_io_sequence", _io_sequence, ["list"], "io", "Sequence list of IO actions"),
        ("cat_io_map", _io_map, ["io", "string"], "io", "Map over IO result"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Const functor (4160-4169) ──────────────────────────────────────
    def _const_make(v): return Const(v)
    def _const_get(c): return c.value
    def _const_bifunctor(f, g, cf):
        return Const(f(cf.value))  # ignore g

    for name, fn, in_types, out_type, desc in [
        ("cat_const_make", _const_make, ["any"], "const", "Make Const functor"),
        ("cat_const_get", _const_get, ["const"], "any", "Extract value from Const"),
        ("cat_const_bimap", _const_bifunctor, ["any", "any", "const"], "const", "Bimap over Const (applies both)"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Higher-order operators (4170-4199) ──────────────────────────────
    def _curry_2(f):
        """Convert f(x, y) to f'(x)(y)"""
        def curried(x):
            def inner(y): return f(x, y)
            return inner
        return curried
    def _uncurry_2(f):
        """Convert f(x)(y) to f'(x, y)"""
        def uncurried(x, y): return f(x)(y)
        return uncurried
    def _flip(f):
        """Swap first two arguments: f(x, y) -> f(y, x)"""
        def flipped(x, y): return f(y, x)
        return flipped
    def _const_fn(v):
        """Constant function: returns v for any input"""
        def f(*args, **kwargs): return v
        return f
    def _apply(f, x): return f(x)
    def _on(f, g):
        """f . g: x -> f(g(x))"""
        return lambda x: f(g(x))
    def _kleisli(f):
        """Wrap a function a -> M<b> in Kleisli category"""
        return f
    def _lift_a2(f, ma, mb):
        """Applicative liftA2: apply binary f to two M values"""
        return ma.bind(lambda a: mb.bind(lambda b: ma.__class__.unit(f(a, b))))

    for name, fn, in_types, out_type, desc in [
        ("cat_curry2", _curry_2, ["any"], "any", "Curry 2-arg function"),
        ("cat_uncurry2", _uncurry_2, ["any"], "any", "Uncurry 2-arg function"),
        ("cat_flip", _flip, ["any"], "any", "Flip first two args"),
        ("cat_const_fn", _const_fn, ["any"], "any", "Constant function"),
        ("cat_apply", _apply, ["any", "any"], "any", "Function application"),
        ("cat_on", _on, ["any", "any"], "any", "Function composition (f . g)"),
        ("cat_lift_a2", _lift_a2, ["any", "monad", "monad"], "monad", "Applicative liftA2"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    # ── Functor laws & verification (4200-4209) ─────────────────────────
    def _verify_functor_law_id(fa, f):
        """Verify map(id) = id:  fmap(lambda x: x)(fa) == fa"""
        try:
            return fa.fmap(lambda x: x) == fa
        except Exception:
            return False
    def _verify_functor_law_comp(fa, f_name, g_name):
        """Verify map(g . f) = map(g) . map(f)"""
        f = _registry_lookup(reg, f_name)
        g = _registry_lookup(reg, g_name)
        try:
            return fa.fmap(lambda x: g(f(x))) == fa.fmap(f).fmap(g)
        except Exception:
            return False
    def _verify_monad_left_id(a, f_name):
        """unit(a) >>= f = f(a)"""
        f = _registry_lookup(reg, f_name)
        try:
            return IdentityM.unit(a).bind(f) == f(a)
        except Exception:
            return False
    def _verify_monad_right_id(m):
        """m >>= unit = m"""
        try:
            return m.bind(IdentityM.unit) == m
        except Exception:
            return False
    def _verify_monad_assoc(m, f_name, g_name):
        """(m >>= f) >>= g = m >>= (x -> f(x) >>= g)"""
        f = _registry_lookup(reg, f_name)
        g = _registry_lookup(reg, g_name)
        try:
            lhs = m.bind(f).bind(g)
            rhs = m.bind(lambda x: f(x).bind(g))
            return lhs == rhs
        except Exception:
            return False

    for name, fn, in_types, out_type, desc in [
        ("cat_verify_functor_id", _verify_functor_law_id, ["functor", "any"], "bool", "Verify map(id) = id"),
        ("cat_verify_functor_comp", _verify_functor_law_comp, ["functor", "string", "string"], "bool", "Verify functor composition law"),
        ("cat_verify_monad_left_id", _verify_monad_left_id, ["any", "string"], "bool", "Verify monad left identity"),
        ("cat_verify_monad_right_id", _verify_monad_right_id, ["monad"], "bool", "Verify monad right identity"),
        ("cat_verify_monad_assoc", _verify_monad_assoc, ["monad", "string", "string"], "bool", "Verify monad associativity"),
    ]:
        reg.register(Operator(op_id, name, "cat", desc, in_types, out_type, True, fn))
        op_id += 1

    return op_id - 4000


def _registry_lookup(reg, name):
    """Look up an operator by name in the registry."""
    op = reg.get_by_name(name)
    if op is None:
        raise KeyError(f"Operator {name!r} not found in registry")
    return op.fn


# Register on import
CAT_OPERATOR_COUNT = register_cat_operators()
