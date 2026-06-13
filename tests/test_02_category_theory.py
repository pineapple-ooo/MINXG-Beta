"""Category Theory: morphisms, functors, monads, Yoneda."""
import minxg.cat as cat
from minxg.cat import MaybeM, IdentityM, State, yoneda_embedding


def test_morphism_composition_typed():
    f = cat.Morphism("int_to_str", (cat.Type("int"),), cat.Type("string"), str)
    g = cat.Morphism("str_to_len", (cat.Type("string"),), cat.Type("int"), len)
    pipe = f >> g
    assert pipe(42) == 2
    assert pipe("hello") == 5


def test_morphism_composition_type_error():
    f = cat.Morphism("int_to_str", (cat.Type("int"),), cat.Type("string"), str)
    h = cat.Morphism("int_to_float", (cat.Type("int"),), cat.Type("float"), float)
    with pytest.raises(TypeError):
        f >> h


def test_maybe_functor_law_identity():
    m = MaybeM.just(7)
    assert m.map(lambda x: x) == m


def test_maybe_functor_law_composition():
    m = MaybeM.just(7)
    f = lambda x: x + 1
    g = lambda x: x * 2
    assert m.map(f).map(g) == m.map(lambda x: g(f(x)))


def test_maybe_monad_left_identity():
    f = lambda x: MaybeM.just(x * 2)
    assert MaybeM.just(7).bind(f) == f(7)


def test_identity_monad_laws():
    def double(x): return IdentityM.unit(x * 2)
    assert IdentityM.unit(7).bind(double) == double(7)
    assert IdentityM.unit(7).bind(IdentityM.unit) == IdentityM.unit(7)


def test_state_monad_threads_state():
    program = (
        State.get()
        .bind(lambda x: State.put(x * 10))
        .bind(lambda _: State.get())
    )
    new_state, result = program.run(5)
    assert new_state == 50
    assert result == 50


def test_yoneda_encoding():
    def op(x): return x * x + 1
    rep = yoneda_embedding(op, [0, 1, 2, 3, 5, 10])
    assert rep == [1, 2, 5, 10, 26, 101]


import pytest
