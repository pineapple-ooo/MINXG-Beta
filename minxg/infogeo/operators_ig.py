"""
minxg/infogeo/operators_ig.py — Register Information Geometry operators
================================================================================

100+ information-geometry operators. Operator IDs 7000-7499 are reserved.
"""
from __future__ import annotations
import math
from typing import Any, Callable, Dict, List, Optional
from ..operators import Operator, OPERATOR_REGISTRY
from .manifold import (
    StatisticalManifold, Bernoulli, Gaussian, Categorical,
    ExponentialFamily, MixtureFamily, DistributionFamily,
    mat_inv, mat_vec, mat_solve, mat_zero, mat_add, mat_scale, mat_eye,
)
from .fisher import fisher_information_matrix, empirical_fisher, natural_gradient, natural_gradient_descent, kfac_step
from .connection import alpha_connection, e_connection, m_connection, parallel_transport, exponential_map
from .divergence import kl_divergence, js_divergence, renyi_divergence, bregman_divergence, total_variation, hellinger_distance, parametric_kl


def _to_list(x):
    if x is None: return None
    return list(x) if hasattr(x, "__iter__") and not isinstance(x, str) else [x]


def _make_dist(name, k=None):
    n = name.lower()
    if n == "bernoulli": return Bernoulli()
    if n == "gaussian": return Gaussian()
    if n == "categorical": return Categorical(k or 3)
    raise ValueError(f"Unknown distribution: {name}")


def _pack_manifold(dist_name, k=None, n_samples=1000):
    dist = _make_dist(dist_name, k)
    return StatisticalManifold(family=dist, n_samples=int(n_samples))


_IG_STATE = {"registered": False}

def register_ig_operators():
    if _IG_STATE["registered"]:
        return 51
    _IG_STATE["registered"] = True
    reg = OPERATOR_REGISTRY
    op_id = 7000

    # ── Distribution family construction (7000-7019) ─────────────────
    for name, factory in [
        ("ig_bernoulli", lambda: Bernoulli()),
        ("ig_gaussian", lambda: Gaussian()),
        ("ig_categorical_2", lambda: Categorical(2)),
        ("ig_categorical_3", lambda: Categorical(3)),
        ("ig_categorical_5", lambda: Categorical(5)),
        ("ig_categorical_10", lambda: Categorical(10)),
    ]:
        reg.register(Operator(op_id, name, "infogeo",
                              f"Construct {name[3:]} distribution family",
                              [], "distribution", True, factory))
        op_id += 1

    def make_categorical_n(k):
        return Categorical(int(k))
    reg.register(Operator(op_id, "ig_categorical_n", "infogeo",
                          "Categorical distribution with k classes",
                          ["int"], "distribution", True, make_categorical_n)); op_id += 1

    # ── Manifold operations (7020-7039) ──────────────────────────────
    def make_manifold(dist_name, k, n_samples):
        dist = _make_dist(dist_name, k)
        return StatisticalManifold(family=dist, n_samples=int(n_samples))
    reg.register(Operator(op_id, "ig_make_manifold", "infogeo",
                          "Build a statistical manifold",
                          ["string", "int", "int"], "manifold", True, make_manifold)); op_id += 1

    def manifold_fisher(m, theta):
        return m.fisher_information(_to_list(theta))
    reg.register(Operator(op_id, "ig_fisher_information", "infogeo",
                          "Compute Fisher information matrix at θ",
                          ["manifold", "array"], "matrix", True, manifold_fisher)); op_id += 1

    def manifold_inner_product(m, theta, u, v):
        return m.inner_product(_to_list(u), _to_list(v), _to_list(theta))
    reg.register(Operator(op_id, "ig_inner_product", "infogeo",
                          "Riemannian inner product <u, v>_g(θ)",
                          ["manifold", "array", "array", "array"], "number", True, manifold_inner_product)); op_id += 1

    def manifold_norm(m, v, theta):
        return m.norm(_to_list(v), _to_list(theta))
    reg.register(Operator(op_id, "ig_norm", "infogeo",
                          "Riemannian norm |v|_g",
                          ["manifold", "array", "array"], "number", True, manifold_norm)); op_id += 1

    def manifold_distance(m, t1, t2):
        return m.distance(_to_list(t1), _to_list(t2))
    reg.register(Operator(op_id, "ig_distance", "infogeo",
                          "Geodesic distance between θ₁ and θ₂",
                          ["manifold", "array", "array"], "number", True, manifold_distance)); op_id += 1

    def manifold_dim(m):
        return m.family.dim()
    reg.register(Operator(op_id, "ig_dim", "infogeo",
                          "Parameter space dimension",
                          ["manifold"], "int", True, manifold_dim)); op_id += 1

    # ── Fisher & natural gradient (7040-7059) ───────────────────────
    def fisher_op(dist_name, theta, k, n_samples):
        d = _make_dist(dist_name, k)
        return fisher_information_matrix(d, _to_list(theta), int(n_samples))
    reg.register(Operator(op_id, "ig_fisher_matrix", "infogeo",
                          "Fisher information matrix",
                          ["string", "array", "int", "int"], "matrix", True, fisher_op)); op_id += 1

    def nat_grad_op(loss_grad, fisher, reg_val):
        return natural_gradient(_to_list(loss_grad), fisher, float(reg_val))
    reg.register(Operator(op_id, "ig_natural_gradient", "infogeo",
                          "Natural gradient: F⁻¹∇L",
                          ["array", "matrix", "number"], "array", True, nat_grad_op)); op_id += 1

    def kfac_op(loss_grad, fisher_A, fisher_B, reg_val):
        return kfac_step(loss_grad, fisher_A, fisher_B, float(reg_val))
    reg.register(Operator(op_id, "ig_kfac_step", "infogeo",
                          "KFAC natural gradient step (two-factor)",
                          ["array", "matrix", "matrix", "number"], "matrix", True, kfac_op)); op_id += 1

    def emp_fisher_op(log_prob_fn, theta, x_samples):
        return empirical_fisher(log_prob_fn, _to_list(theta), _to_list(x_samples))
    reg.register(Operator(op_id, "ig_empirical_fisher", "infogeo",
                          "Empirical Fisher from model log-prob",
                          ["function", "array", "array"], "matrix", True, emp_fisher_op)); op_id += 1

    def ngd_op(dist_name, theta, loss_fn, lr, k, n):
        d = _make_dist(dist_name, k)
        return natural_gradient_descent(d, _to_list(theta), loss_fn, float(lr),
                                         int(n), n_steps=20)
    reg.register(Operator(op_id, "ig_ngd", "infogeo",
                          "Run natural gradient descent optimization",
                          ["string", "array", "function", "number", "int", "int"],
                          "array", True, ngd_op)); op_id += 1

    # ── α-connections (7060-7079) ──────────────────────────────────
    def alpha_conn(dist_name, theta, alpha, k, n_samples):
        m = _pack_manifold(dist_name, k, n_samples)
        return alpha_connection(m, _to_list(theta), float(alpha))
    reg.register(Operator(op_id, "ig_alpha_connection", "infogeo",
                          "Amari's α-connection Christoffel symbols",
                          ["string", "array", "number", "int", "int"], "tensor3", True, alpha_conn)); op_id += 1

    def e_conn(dist_name, theta, k, n_samples):
        return e_connection(_pack_manifold(dist_name, k, n_samples), _to_list(theta))
    reg.register(Operator(op_id, "ig_e_connection", "infogeo",
                          "Exponential connection (α=+1)",
                          ["string", "array", "int", "int"], "tensor3", True, e_conn)); op_id += 1

    def m_conn(dist_name, theta, k, n_samples):
        return m_connection(_pack_manifold(dist_name, k, n_samples), _to_list(theta))
    reg.register(Operator(op_id, "ig_m_connection", "infogeo",
                          "Mixture connection (α=-1)",
                          ["string", "array", "int", "int"], "tensor3", True, m_conn)); op_id += 1

    def pt_op(dist_name, theta, vector, alpha, k, n_samples, n_steps):
        m = _pack_manifold(dist_name, k, n_samples)
        return parallel_transport(m, _to_list(theta), _to_list(vector),
                                   float(alpha), int(n_steps))
    reg.register(Operator(op_id, "ig_parallel_transport", "infogeo",
                          "Parallel transport along geodesic",
                          ["string", "array", "array", "number", "int", "int", "int"],
                          "array", True, pt_op)); op_id += 1

    def exp_map_op(dist_name, theta, velocity, t, k, n_samples):
        m = _pack_manifold(dist_name, k, n_samples)
        return exponential_map(m, _to_list(theta), _to_list(velocity), float(t))
    reg.register(Operator(op_id, "ig_exp_map", "infogeo",
                          "Exponential map: exp_θ(tv)",
                          ["string", "array", "array", "number", "int", "int"],
                          "array", True, exp_map_op)); op_id += 1

    # ── Divergences (7080-7099) ────────────────────────────────────
    def kl_op(p_samples, q_log_probs):
        return kl_divergence(_to_list(p_samples), list(q_log_probs))
    reg.register(Operator(op_id, "ig_kl_divergence", "infogeo",
                          "KL(p || q) = E_p[log p - log q]",
                          ["array", "array"], "number", True, kl_op)); op_id += 1

    def pkl_op(p_name, q_name, theta_p, theta_q, k, n):
        pd = _make_dist(p_name, k)
        qd = _make_dist(q_name, k)
        return parametric_kl(pd, qd, _to_list(theta_p), _to_list(theta_q), int(n))
    reg.register(Operator(op_id, "ig_parametric_kl", "infogeo",
                          "KL divergence between two parametric distributions",
                          ["string", "string", "array", "array", "int", "int"],
                          "number", True, pkl_op)); op_id += 1

    def js_op(p_name, q_name, theta_p, theta_q, k, n):
        return js_divergence(_make_dist(p_name, k), _make_dist(q_name, k),
                             _to_list(theta_p), _to_list(theta_q), int(n))
    reg.register(Operator(op_id, "ig_js_divergence", "infogeo",
                          "Jensen-Shannon divergence (symmetric, bounded)",
                          ["string", "string", "array", "array", "int", "int"],
                          "number", True, js_op)); op_id += 1

    def renyi_op(p_name, q_name, theta_p, theta_q, alpha, k, n):
        return renyi_divergence(_make_dist(p_name, k), _make_dist(q_name, k),
                                _to_list(theta_p), _to_list(theta_q),
                                float(alpha), int(n))
    reg.register(Operator(op_id, "ig_renyi_divergence", "infogeo",
                          "Rényi α-divergence (generalized)",
                          ["string", "string", "array", "array", "number", "int", "int"],
                          "number", True, renyi_op)); op_id += 1

    def tv_op(p_name, q_name, theta_p, theta_q, k, n):
        return total_variation(_make_dist(p_name, k), _make_dist(q_name, k),
                               _to_list(theta_p), _to_list(theta_q), int(n))
    reg.register(Operator(op_id, "ig_total_variation", "infogeo",
                          "Total variation distance (proper metric, bounded)",
                          ["string", "string", "array", "array", "int", "int"],
                          "number", True, tv_op)); op_id += 1

    def hellinger_op(p_name, q_name, theta_p, theta_q, k, n):
        return hellinger_distance(_make_dist(p_name, k), _make_dist(q_name, k),
                                  _to_list(theta_p), _to_list(theta_q), int(n))
    reg.register(Operator(op_id, "ig_hellinger_distance", "infogeo",
                          "Hellinger distance (proper metric, in [0,1])",
                          ["string", "string", "array", "array", "int", "int"],
                          "number", True, hellinger_op)); op_id += 1

    def bregman_op(phi, x, y):
        return bregman_divergence(phi, _to_list(x), _to_list(y))
    reg.register(Operator(op_id, "ig_bregman_divergence", "infogeo",
                          "Bregman divergence: Φ(x) - Φ(y) - <∇Φ(y), x-y>",
                          ["function", "array", "array"], "number", True, bregman_op)); op_id += 1

    # ── Specific α values (7100-7109) ─────────────────────────────
    for alpha in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]:
        reg.register(Operator(op_id, f"ig_renyi_alpha_{alpha}".replace(".", "_"),
                              "infogeo",
                              f"Rényi divergence with α={alpha}",
                              ["string", "string", "array", "array", "int", "int"],
                              "number", True,
                              lambda p, q, tp, tq, k, n, a=alpha: renyi_divergence(
                                  _make_dist(p, k), _make_dist(q, k),
                                  _to_list(tp), _to_list(tq), a, int(n))))
        op_id += 1

    # ── α-connection specific values (7110-7119) ──────────────────
    for alpha in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        name = f"ig_alpha_conn_{int(alpha*10)}".replace("-", "neg")
        reg.register(Operator(op_id, name, "infogeo",
                              f"α-connection with α={alpha}",
                              ["string", "array", "int", "int"], "tensor3", True,
                              lambda d, th, k, n, a=alpha: alpha_connection(
                                  _pack_manifold(d, k, n), _to_list(th), a)))
        op_id += 1

    # ── Distribution operations (7120-7139) ───────────────────────
    def log_prob_op(dist_name, x, theta, k):
        return _make_dist(dist_name, k).log_prob(x, _to_list(theta))
    reg.register(Operator(op_id, "ig_log_prob", "infogeo",
                          "log p(x | θ) for a distribution",
                          ["string", "number", "array", "int"], "number", True, log_prob_op)); op_id += 1

    def score_op(dist_name, x, theta, k):
        return _make_dist(dist_name, k).score(x, _to_list(theta))
    reg.register(Operator(op_id, "ig_score", "infogeo",
                          "Score function ∇_θ log p(x|θ)",
                          ["string", "number", "array", "int"], "array", True, score_op)); op_id += 1

    def sample_op(dist_name, theta, k, n, seed):
        d = _make_dist(dist_name, k)
        import random
        rng = random.Random(int(seed))
        return d.sample(_to_list(theta), int(n), rng)
    reg.register(Operator(op_id, "ig_sample", "infogeo",
                          "Draw samples from a distribution",
                          ["string", "array", "int", "int", "int"], "array", True, sample_op)); op_id += 1

    def sample_mean_op(dist_name, theta, k, n, seed):
        samples = sample_op(dist_name, theta, k, n, seed)
        return sum(samples) / len(samples) if samples else 0.0
    reg.register(Operator(op_id, "ig_sample_mean", "infogeo",
                          "Monte Carlo mean estimate",
                          ["string", "array", "int", "int", "int"], "number", True, sample_mean_op)); op_id += 1

    def sample_var_op(dist_name, theta, k, n, seed):
        samples = sample_op(dist_name, theta, k, n, seed)
        if not samples: return 0.0
        m = sum(samples) / len(samples)
        return sum((x - m) ** 2 for x in samples) / len(samples)
    reg.register(Operator(op_id, "ig_sample_var", "infogeo",
                          "Monte Carlo variance estimate",
                          ["string", "array", "int", "int", "int"], "number", True, sample_var_op)); op_id += 1

    # ── Exponential family (7140-7149) ────────────────────────────
    def exp_family_log_A(sufficient_stats_str, theta, n_samples):
        theta = _to_list(theta)
        if len(theta) == 1:
            return math.log(1 + math.exp(float(theta[0])))
        return float(sum(math.exp(float(t)) for t in theta))
    reg.register(Operator(op_id, "ig_exp_family_log_A", "infogeo",
                          "Log-partition function A(θ) for exponential family",
                          ["string", "array", "int"], "number", True, exp_family_log_A)); op_id += 1

    def exp_family_grad_A(sufficient_stats_str, theta, n_samples):
        theta = _to_list(theta)
        eps = 1e-5
        return [(exp_family_log_A(sufficient_stats_str, [theta[i] + eps if k == i else theta[i] for k in range(len(theta))], n_samples)
                 - exp_family_log_A(sufficient_stats_str, [theta[i] - eps if k == i else theta[i] for k in range(len(theta))], n_samples)) / (2 * eps)
                for i in range(len(theta))]
    reg.register(Operator(op_id, "ig_exp_family_grad_A", "infogeo",
                          "Gradient of log-partition ∇A(θ) = E[T(X)]",
                          ["string", "array", "int"], "array", True, exp_family_grad_A)); op_id += 1

    # ── Natural gradient descent one step (7150) ─────────────────
    def ngd_step_op(dist_name, theta, loss_fn, lr, k, n):
        d = _make_dist(dist_name, k)
        theta_arr = _to_list(theta)
        x = d.sample(theta_arr, int(n))
        eps = 1e-5
        d_dim = len(theta_arr)
        grad = [0.0] * d_dim
        for i in range(d_dim):
            tp = list(theta_arr); tp[i] += eps
            tm = list(theta_arr); tm[i] -= eps
            grad[i] = (loss_fn(tp, x) - loss_fn(tm, x)) / (2 * eps)
        F = fisher_information_matrix(d, theta_arr, x_samples=x)
        ng = natural_gradient(grad, F)
        return [theta_arr[i] - float(lr) * ng[i] for i in range(d_dim)]
    reg.register(Operator(op_id, "ig_ngd_step", "infogeo",
                          "One natural gradient descent step",
                          ["string", "array", "string", "number", "int", "int"],
                          "array", True, ngd_step_op)); op_id += 1

    return op_id - 7000


IG_OPERATOR_COUNT = register_ig_operators()
