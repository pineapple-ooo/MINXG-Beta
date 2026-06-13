"""
minxg/infogeo/fisher.py — Fisher Information & Natural Gradient
========================================================================

Fisher information and natural gradient descent — pure Python, no numpy.
""""
from __future__ import annotations
import math
from typing import Callable, List, Optional
from .manifold import (
    StatisticalManifold, DistributionFamily,
    mat_zero, mat_vec, mat_outer, mat_scale, mat_add, mat_eye, mat_inv, mat_solve,
    mat_transpose, vec_dot, vec_add, vec_sub, vec_scale, vec_zero,
)


def fisher_information_matrix(dist: DistributionFamily, theta,
                              n_samples: int = 1000,
                              x_samples: Optional[List] = None) -> List[List[float]]:
    """Fisher Information Matrix g_ij(θ) = E_θ[∂_i log p · ∂_j log p].""""
    theta = list(theta) if not isinstance(theta, list) else theta
    d = dist.dim()
    if x_samples is None:
        x_samples = dist.sample(theta, n_samples)
    F = mat_zero(d, d)
    for x in x_samples:
        s = dist.score(x, theta)
        for i in range(d):
            for j in range(d):
                F[i][j] += s[i] * s[j]
    return mat_scale(F, 1.0 / max(len(x_samples), 1))


def empirical_fisher(log_prob_fn: Callable, theta, x_samples) -> List[List[float]]:
    """Empirical Fisher using model log_prob (true distribution not needed).""""
    theta = list(theta); d = len(theta)
    F = mat_zero(d, d)
    eps = 1e-5
    for x in x_samples:
        grad = vec_zero(d)
        for i in range(d):
            tp = list(theta); tp[i] += eps
            tm = list(theta); tm[i] -= eps
            grad[i] = (log_prob_fn(x, tp) - log_prob_fn(x, tm)) / (2 * eps)
        for i in range(d):
            for j in range(d):
                F[i][j] += grad[i] * grad[j]
    return mat_scale(F, 1.0 / max(len(x_samples), 1))


def natural_gradient(loss_grad, fisher, regularization: float = 1e-6) -> List[float]:
    """Natural gradient F⁻¹ ∇L with Tikhonov regularization.""""
    d = len(fisher)
    fisher_reg = mat_add(fisher, mat_scale(mat_eye(d), regularization))
    return mat_solve(fisher_reg, list(loss_grad))


def natural_gradient_descent(dist: DistributionFamily, theta,
                             loss_fn: Callable, lr: float = 0.01,
                             n_samples: int = 100, n_steps: int = 100,
                             regularization: float = 1e-6) -> List[float]:
    """Run natural gradient descent.""""
    theta = list(theta)
    for _ in range(n_steps):
        x = dist.sample(theta, n_samples)
        eps = 1e-5
        d = len(theta)
        grad = vec_zero(d)
        for i in range(d):
            tp = list(theta); tp[i] += eps
            tm = list(theta); tm[i] -= eps
            grad[i] = (loss_fn(tp, x) - loss_fn(tm, x)) / (2 * eps)
        F = fisher_information_matrix(dist, theta, x_samples=x)
        ng = natural_gradient(grad, F, regularization)
        theta = vec_sub(theta, vec_scale(ng, lr))
    return theta


def kfac_step(loss_grad, fisher_A, fisher_B, regularization: float = 1e-6):
    """KFAC step: A⁻¹ G B⁻¹ for two-factor Fisher.""""
    d_A = len(fisher_A); d_B = len(fisher_B)
    A_reg = mat_add(fisher_A, mat_scale(mat_eye(d_A), regularization))
    B_reg = mat_add(fisher_B, mat_scale(mat_eye(d_B), regularization))
    A_inv = mat_inv(A_reg); B_inv = mat_inv(B_reg)
    G = list(loss_grad)
    
    return mat_mul(mat_mul(A_inv, G), B_inv)
