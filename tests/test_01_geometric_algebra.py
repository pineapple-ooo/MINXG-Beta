"""Geometric Algebra correctness — the bedrock of the GA pillar."""
import math
import pytest
from minxg.ga import Multivector, Signature, Rotor, Reflector, Dilator


def test_euclidean_squared_bases():
    sig = Signature(3, 0)
    e1 = Multivector({1: 1.0}, sig)
    e2 = Multivector({2: 1.0}, sig)
    e3 = Multivector({4: 1.0}, sig)
    assert e1 * e1 == Multivector.scalar(1.0, sig)
    assert e2 * e2 == Multivector.scalar(1.0, sig)
    assert e3 * e3 == Multivector.scalar(1.0, sig)


def test_bivector_squared_is_minus_one():
    sig = Signature(3, 0)
    e1 = Multivector({1: 1.0}, sig)
    e2 = Multivector({2: 1.0}, sig)
    B = e1.outer(e2)
    B_sq = B * B
    assert B_sq[0] == pytest.approx(-1.0, abs=1e-9)
    assert sum(B_sq.coeffs.values()) == pytest.approx(-1.0, abs=1e-9)


def test_rotor_rotates_vector_in_plane():
    sig = Signature(3, 0)
    e1 = Multivector({1: 1.0}, sig)
    e2 = Multivector({2: 1.0}, sig)
    B = e1.outer(e2)
    R = Rotor.from_bivector(B, math.pi / 2)
    rotated = R.apply(e1)
    assert rotated[2] == pytest.approx(1.0, abs=1e-9)
    assert abs(rotated[1]) < 1e-9


def test_rotor_is_orthogonal():
    """Rotor preserves length: |R(v)| = |v|."""
    sig = Signature(3, 0)
    e1 = Multivector({1: 1.0}, sig)
    e3 = Multivector({4: 1.0}, sig)
    B = e3.outer(e1)
    R = Rotor.from_bivector(B, math.pi / 3)
    v = Multivector({1: 3.0, 2: 4.0, 4: 0.0}, sig)
    v_rot = R.apply(v)
    assert v.norm == pytest.approx(v_rot.norm, abs=1e-9)


def test_reflector_reverses_component():
    sig = Signature(3, 0)
    e2 = Multivector({2: 1.0}, sig)
    n = Multivector({1: 1.0, 2: 0.0, 4: 0.0}, sig)
    ref = Reflector.from_normal(n)
    reflected = ref.apply(e2)
    assert reflected[2] == pytest.approx(-1.0, abs=1e-9)


def test_dilator_scales_uniformly():
    sig = Signature(3, 0)
    e1 = Multivector({1: 3.0, 2: 4.0, 4: 0.0}, sig)
    D = Dilator.from_scale(2.0, sig)
    scaled = D.apply(e1)
    assert scaled[1] == pytest.approx(6.0)
    assert scaled[2] == pytest.approx(8.0)
