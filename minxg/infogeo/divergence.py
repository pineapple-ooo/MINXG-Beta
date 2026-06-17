"""
minxg/infogeo/divergence.py — Information Divergences (pure Python)
============================================================================

All divergences implemented in pure Python without numpy.
"""
from __future__ import annotations
import math
from typing import Callable, List
from .manifold import DistributionFamily


def kl_divergence(p_samples, q_log_prob, support=(-10, 10)) -> float:
    """KL(p || q) via samples from p (KDE-estimated log p)."""
    p_samples = list(p_samples)
    n = len(p_samples)
    if n == 0: return 0.0
    bandwidth = max((sum((x - sum(p_samples) / n) ** 2 for x in p_samples) / n) ** 0.5
                    * (4 / (3 * n)) ** (1/5), 1e-6)

    def log_p(x):
        u = [(x - xi) / bandwidth for xi in p_samples]
        log_terms = [-0.5 * ui * ui - math.log(bandwidth) - 0.5 * math.log(2 * math.pi) for ui in u]
        max_lt = max(log_terms)
        return max_lt + math.log(sum(math.exp(lt - max_lt) for lt in log_terms) / n)

    total = 0.0
    for x in p_samples:
        lp = log_p(x)
        lq = q_log_prob(x) if callable(q_log_prob) else float(q_log_prob)
        total += lp - lq
    return total / n


def parametric_kl(p_dist, q_dist, theta_p, theta_q, n_samples: int = 1000) -> float:
    """KL(p || q) for parametric distributions."""
    x = p_dist.sample(theta_p, n_samples)
    total = 0.0
    for xi in x:
        total += p_dist.log_prob(xi, theta_p) - q_dist.log_prob(xi, theta_q)
    return total / n_samples


def _logsumexp_2(a: float, b: float) -> float:
    if a > b: return a + math.log(1 + math.exp(b - a))
    return b + math.log(1 + math.exp(a - b))


def js_divergence(p_dist, q_dist, theta_p, theta_q, n_samples: int = 1000) -> float:
    """Jensen-Shannon divergence (symmetric, bounded in [0, ln 2])."""
    p_samples = p_dist.sample(theta_p, n_samples // 2)
    q_samples = q_dist.sample(theta_q, n_samples // 2)

    def kl_from_samples(samples, from_p):
        total = 0.0
        for x in samples:
            lp = p_dist.log_prob(x, theta_p)
            lq = q_dist.log_prob(x, theta_q)
            lm = math.log(0.5) + _logsumexp_2(lp, lq)
            if from_p: total += lp - lm
            else: total += lq - lm
        return total / max(len(samples), 1)

    return 0.5 * (kl_from_samples(p_samples, True) + kl_from_samples(q_samples, False))


def renyi_divergence(p_dist, q_dist, theta_p, theta_q, alpha: float = 2.0,
                     n_samples: int = 1000) -> float:
    """Rényi α-divergence. α=1 recovers KL."""
    if abs(alpha - 1) < 1e-9:
        return parametric_kl(p_dist, q_dist, theta_p, theta_q, n_samples)
    samples = p_dist.sample(theta_p, n_samples)
    total = 0.0
    for x in samples:
        lp = p_dist.log_prob(x, theta_p)
        lq = q_dist.log_prob(x, theta_q)
        total += math.exp((1 - alpha) * (lp - lq))
    avg = total / n_samples
    if avg <= 0: return float('inf')
    return math.log(avg) / (alpha - 1)


def bregman_divergence(phi: Callable, x, y) -> float:
    """Bregman divergence D_Φ(x, y) = Φ(x) - Φ(y) - <∇Φ(y), x - y>."""
    x = list(x); y = list(y)
    eps = 1e-6
    d = len(x)
    def grad_phi(z):
        g = [0.0] * d
        for i in range(d):
            zp = list(z); zp[i] += eps
            zm = list(z); zm[i] -= eps
            g[i] = (phi(zp) - phi(zm)) / (2 * eps)
        return g
    g = grad_phi(y)
    return phi(x) - phi(y) - sum(g[i] * (x[i] - y[i]) for i in range(d))


def total_variation(p_dist, q_dist, theta_p, theta_q, n_samples: int = 2000) -> float:
    """Total variation distance."""
    p_samples = p_dist.sample(theta_p, n_samples // 2)
    q_samples = q_dist.sample(theta_q, n_samples // 2)
    total = 0.0
    count = 0
    for x in list(p_samples) + list(q_samples):
        p_val = math.exp(p_dist.log_prob(x, theta_p))
        q_val = math.exp(q_dist.log_prob(x, theta_q))
        total += abs(p_val - q_val)
        count += 1
    return 0.5 * total / max(count, 1)


def hellinger_distance(p_dist, q_dist, theta_p, theta_q, n_samples: int = 2000) -> float:
    """Hellinger distance in [0, 1]."""
    p_samples = p_dist.sample(theta_p, n_samples // 2)
    q_samples = q_dist.sample(theta_q, n_samples // 2)
    total = 0.0
    count = 0
    for x in list(p_samples) + list(q_samples):
        lp = p_dist.log_prob(x, theta_p)
        lq = q_dist.log_prob(x, theta_q)
        l_p_over_m = 0.5 * (lp + math.log(2) - _logsumexp_2(lp, lq))
        l_q_over_m = 0.5 * (lq + math.log(2) - _logsumexp_2(lp, lq))
        total += (math.exp(l_p_over_m) - math.exp(l_q_over_m)) ** 2
        count += 1
    return math.sqrt(0.5 * total / max(count, 1))
