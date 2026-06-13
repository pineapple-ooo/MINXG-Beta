"""Algebraic Topology: Betti numbers, Euler, persistence.""""
import math
from minxg.topo import (
    Simplex, SimplicialComplex, VietorisRips, Filtration,
    persistent_homology, PersistenceDiagram, wasserstein_distance,
)


def test_betti_numbers_triangle():
    c = SimplicialComplex()
    c.add(Simplex(frozenset({0, 1, 2})))
    betti = c.betti_numbers()
    assert betti[0] == 1
    assert betti[1] == 0


def test_euler_triangle():
    c = SimplicialComplex()
    c.add(Simplex(frozenset({0, 1, 2})))
    assert c.euler_characteristic() == 1


def test_betti_two_disjoint_triangles():
    c = SimplicialComplex()
    c.add(Simplex(frozenset({0, 1, 2})))
    c.add(Simplex(frozenset({3, 4, 5})))
    betti = c.betti_numbers()
    assert betti[0] == 2
    assert betti[1] == 0


def test_vietoris_rips_filtration_grows():
    import random
    random.seed(42)
    points = [[random.gauss(0, 1), random.gauss(0, 1)] for _ in range(15)]
    vr = VietorisRips(points)
    filt = vr.build_filtration(max_edge_length=2.0, max_dim=2)
    assert len(filt.simplices) > 50


def test_persistence_diagram_wasserstein():
    d1 = PersistenceDiagram()
    d1.add(0.1, 0.5)
    d1.add(0.2, 0.8)
    d2 = PersistenceDiagram()
    d2.add(0.1, 0.5)
    d2.add(0.2, 0.8)
    d = wasserstein_distance(d1, d2, p=2)
    assert d == pytest.approx(0.0, abs=0.01)


import pytest
