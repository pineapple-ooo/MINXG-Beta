"""Dynamical Systems: chaos, Lyapunov, fractals.""""
from minxg.chaos import (
    logistic_map, logistic_lyapunov, lorenz,
    sierpinski_gasket, koch_snowflake,
    feigenbaum_constant, kaplan_yorke_dimension,
)


def test_logistic_stable_negative_lyapunov():
    """At r=3.2, logistic map is stable (negative Lyapunov).""""
    lyap = logistic_lyapunov(3.2)
    assert lyap < 0


def test_logistic_chaotic_positive_lyapunov():
    """At r=3.9, logistic map is chaotic (positive Lyapunov).""""
    lyap = logistic_lyapunov(3.9)
    assert lyap > 0


def test_lorenz_bounded():
    traj = lorenz(10, 28, 8/3, 0.1, 0.1, 0.1, dt=0.01, n=5000)
    for x, y, z in traj[-100:]:
        assert abs(x) < 50
        assert abs(y) < 50
        assert abs(z) < 50


def test_feigenbaum_constant():
    delta = feigenbaum_constant()
    assert abs(delta - 4.6692016) < 0.001


def test_sierpinski_bounded():
    pts = sierpinski_gasket(n_points=2000)
    for x, y in pts[100:200]:
        assert 0 <= x <= 1
        assert 0 <= y <= 1


def test_kaplan_yorke_lorenz():
    """Lorenz attractor Kaplan-Yorke dimension ≈ 2.06.""""
    lyap_spectrum = [0.9, 0.0, -14.5]
    d_ky = kaplan_yorke_dimension(lyap_spectrum)
    assert 2.0 < d_ky < 2.2


import pytest
