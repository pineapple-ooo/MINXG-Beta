"""
minxg/infogeo/connection.py — α-Connections (pure Python)
=================================================================

Amari's α-connection on statistical manifolds — pure Python.
""""
from __future__ import annotations
import math
from typing import List, Optional
from .manifold import (
    StatisticalManifold, DistributionFamily,
    mat_zero, vec_zero, vec_scale, vec_add, vec_sub, vec_norm,
)


def alpha_connection(manifold: StatisticalManifold, theta, alpha: float) -> List[List[List[float]]]:
    """Amari's α-connection Christoffel symbols (3-tensor).""""
    theta = list(theta)
    d = manifold.family.dim()
    x_samples = manifold.family.sample(theta, manifold.n_samples)

    def log_p(x, th):
        return manifold.family.log_prob(x, th)

    def first_deriv(x, th):
        eps = 1e-5
        g = vec_zero(d)
        for i in range(d):
            tp = list(th); tp[i] += eps
            tm = list(th); tm[i] -= eps
            g[i] = (log_p(x, tp) - log_p(x, tm)) / (2 * eps)
        return g

    def second_deriv(x, th):
        eps = 1e-4
        H = mat_zero(d, d)
        for i in range(d):
            for j in range(d):
                tpp = list(th); tpp[i] += eps; tpp[j] += eps
                tpm = list(th); tpm[i] += eps; tpm[j] -= eps
                tmp = list(th); tmp[i] -= eps; tmp[j] += eps
                tmm = list(th); tmm[i] -= eps; tmm[j] -= eps
                H[i][j] = (log_p(x, tpp) - log_p(x, tpm) - log_p(x, tmp) + log_p(x, tmm)) / (4 * eps * eps)
        return H

    Gamma = [[[0.0] * d for _ in range(d)] for _ in range(d)]
    for x in x_samples:
        s = first_deriv(x, theta)
        H = second_deriv(x, theta)
        for i in range(d):
            for j in range(d):
                for k in range(d):
                    Gamma[i][j][k] += H[i][j] * s[k]
        for i in range(d):
            for j in range(d):
                for k in range(d):
                    Gamma[i][j][k] += (1 - alpha) / 2 * s[i] * s[j] * s[k]
        for i in range(d):
            for j in range(d):
                for k in range(d):
                    Gamma[i][j][k] -= (1 + alpha) / 2 * s[j] * s[i] * s[k]
    n = max(len(x_samples), 1)
    for i in range(d):
        for j in range(d):
            for k in range(d):
                Gamma[i][j][k] /= n
    return Gamma


def e_connection(manifold, theta): return alpha_connection(manifold, theta, 1.0)
def m_connection(manifold, theta): return alpha_connection(manifold, theta, -1.0)


def parallel_transport(manifold, theta, vector, alpha=0.0,
                       n_steps=50, direction=None) -> List[float]:
    """Parallel transport V along geodesic in direction d.""""
    if direction is None:
        n_v = vec_norm(vector) + 1e-12
        direction = vec_scale(vector, 1.0 / n_v)
    direction = list(direction); vector = list(vector); theta = list(theta)
    dt = 1.0 / n_steps
    v = list(vector); cur_theta = list(theta); d = len(v)
    for _ in range(n_steps):
        G = alpha_connection(manifold, cur_theta, alpha)
        dV = vec_zero(d)
        for i in range(d):
            for j in range(d):
                for k in range(d):
                    dV[i] -= G[i][j][k] * v[j] * direction[k] * dt
        v = vec_add(v, dV)
        cur_theta = vec_add(cur_theta, vec_scale(direction, dt))
    return v


def exponential_map(manifold, theta, velocity, t=1.0) -> List[float]:
    """Exponential map on manifold: exp_θ(tv).""""
    theta = list(theta); velocity = list(velocity)
    n_steps = 50; dt = t / n_steps
    cur = list(theta); v = list(velocity); d = len(v)
    for _ in range(n_steps):
        G = alpha_connection(manifold, cur, 0.0)
        dtheta = vec_scale(v, dt)
        dv = vec_zero(d)
        for k in range(d):
            for i in range(d):
                for j in range(d):
                    dv[k] -= G[k][i][j] * v[i] * v[j] * dt
        cur = vec_add(cur, dtheta)
        v = vec_add(v, dv)
    return cur
