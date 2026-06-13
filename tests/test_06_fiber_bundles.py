"""Fiber Bundles: connections, curvature, geodesics, parallel transport.""""
import math
from minxg.fiber import (
    Connection, ParallelTransport, Curvature,
    TangentBundle, RiemannianMetric,
)


def test_zero_connection_zero_curvature():
    conn = Connection(dim=2)
    curv = Curvature(conn)
    R = curv.riemann_tensor([0.0, 0.0])
    max_R = max(abs(R[i][j][k][l]) for i in range(2) for j in range(2) for k in range(2) for l in range(2))
    assert max_R < 1e-9


def test_euclidean_geodesic_is_straight_line():
    tb = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, 1]]))
    geo = tb.geodesic([0, 0], [1, 0], t_max=2.0, n_steps=20)
    assert geo[-1][0] == pytest.approx(2.0, abs=0.01)
    assert geo[-1][1] == pytest.approx(0.0, abs=0.01)


def test_sphere_geodesic_around_equator():
    sphere = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, math.sin(p[0])**2]]))
    geo = sphere.geodesic([math.pi/2, 0], [0, 1], t_max=math.pi, n_steps=50)
    assert abs(geo[-1][1] - math.pi) < 0.05


def test_parallel_transport_along_curve():
    conn = Connection(dim=2)
    pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
    v = pt.transport([1.0, 0.0], n_steps=100)
    assert isinstance(v, list)
    assert len(v) == 2


def test_euclidean_ricci_tensor_zero():
    """For Euclidean metric, the Ricci tensor is identically zero.""""
    conn = Connection(dim=2, christoffel_fn=lambda p: [[[0]*2]*2]*2)
    curv = Curvature(conn)
    Ric = curv.ricci_tensor([0.0, 0.0])
    max_Ric = max(abs(x) for row in Ric for x in row)
    assert max_Ric < 1e-9


import pytest
