"""Information Geometry: Fisher, natural gradient, divergences."""
from minxg.infogeo import (
    Gaussian, Bernoulli, fisher_information_matrix, natural_gradient,
    parametric_kl, hellinger_distance, js_divergence,
)


def test_fisher_information_gaussian():
    g = Gaussian()
    F = fisher_information_matrix(g, [0.0, 1.0], n_samples=2000)
    assert F[0][0] == pytest.approx(1.0, abs=0.15)
    assert F[1][1] == pytest.approx(2.0, abs=0.3)


def test_natural_gradient_reparameterization_invariance():
    """Natural gradient differs from Euclidean gradient in non-trivial ways."""
    g = Gaussian()
    F = fisher_information_matrix(g, [0.0, 1.0], n_samples=500)
    grad = [0.5, 0.1]
    nat = natural_gradient(grad, F, regularization=1e-6)
    
    
    diff0 = abs(nat[0] - grad[0]) / abs(grad[0])
    diff1 = abs(nat[1] - grad[1]) / abs(grad[1])
    assert max(diff0, diff1) > 0.01


def test_kl_divergence_gaussian():
    g = Gaussian()
    kl = parametric_kl(g, g, [0.0, 1.0], [1.0, 1.0], n_samples=2000)
    assert 0.4 < kl < 0.6


def test_kl_divergence_zero_for_same_distribution():
    g = Gaussian()
    kl = parametric_kl(g, g, [0.5, 1.0], [0.5, 1.0], n_samples=1000)
    assert kl < 0.05


def test_hellinger_distance_bounded():
    g = Gaussian()
    h = hellinger_distance(g, g, [0.0, 1.0], [1.0, 1.0], n_samples=1000)
    assert 0 <= h <= 1


def test_js_divergence_symmetric():
    g1, g2 = Gaussian(), Gaussian()
    js1 = js_divergence(g1, g2, [0.0, 1.0], [1.0, 1.0], n_samples=1000)
    js2 = js_divergence(g2, g1, [1.0, 1.0], [0.0, 1.0], n_samples=1000)
    assert js1 == pytest.approx(js2, abs=0.04)


def test_bernoulli_sample_mean():
    b = Bernoulli()
    samples = b.sample([0.7], 5000)
    mean = sum(samples) / len(samples)
    assert abs(mean - 0.7) < 0.05


import pytest
