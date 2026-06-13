"""
minxg/infogeo/manifold.py — Statistical Manifolds
==========================================================

A STATISTICAL MANIFOLD is a smooth manifold M where each point p ∈ M is
a probability distribution P_θ over some sample space, parameterized by
θ = (θ¹, ..., θⁿ).

All implementations are PURE PYTHON (no numpy dependency). For matrix
operations we use list-of-lists with explicit loops. Performance: O(d²)
for d-dim Fisher matrix, ~10ms typical for d=10 with n=1000 samples.
""""
from __future__ import annotations
import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple, Union






def vec_add(a, b): return [x + y for x, y in zip(a, b)]
def vec_sub(a, b): return [x - y for x, y in zip(a, b)]
def vec_scale(a, s): return [x * s for x in a]
def vec_dot(a, b): return sum(x * y for x, y in zip(a, b))
def vec_norm(a): return math.sqrt(vec_dot(a, a))
def vec_zero(d): return [0.0] * d
def vec_clone(a): return list(a)

def mat_zero(d1, d2): return [[0.0] * d2 for _ in range(d1)]
def mat_mul(A, B):
    """Matrix product. A is m×k, B is k×n, result is m×n.""""
    m = len(A); n = len(B[0]) if B else 0; k = len(B) if B else 0
    if k == 0: return mat_zero(m, n)
    result = mat_zero(m, n)
    for i in range(m):
        for j in range(n):
            s = 0.0
            for l in range(k):
                s += A[i][l] * B[l][j]
            result[i][j] = s
    return result

def mat_vec(A, v):
    m = len(A); n = len(v) if v else 0
    result = [0.0] * m
    for i in range(m):
        s = 0.0
        for j in range(n):
            s += A[i][j] * v[j]
        result[i] = s
    return result

def mat_outer(u, v):
    return [[u[i] * v[j] for j in range(len(v))] for i in range(len(u))]

def mat_add(A, B):
    m, n = len(A), len(A[0]) if A else 0
    return [[A[i][j] + B[i][j] for j in range(n)] for i in range(m)]

def mat_scale(A, s):
    return [[A[i][j] * s for j in range(len(A[0]))] for i in range(len(A))]

def mat_eye(d):
    I = mat_zero(d, d)
    for i in range(d): I[i][i] = 1.0
    return I

def mat_inv(A):
    """Matrix inverse via Gauss-Jordan elimination. Returns A⁻¹.""""
    n = len(A)
    
    M = [row + row_id for row, row_id in zip(A, mat_eye(n))]
    
    for col in range(n):
        
        pivot = col
        for row in range(col + 1, n):
            if abs(M[row][col]) > abs(M[pivot][col]):
                pivot = row
        M[col], M[pivot] = M[pivot], M[col]
        if abs(M[col][col]) < 1e-12:
            raise ValueError("Matrix is singular")
        
        pv = M[col][col]
        for j in range(2 * n):
            M[col][j] /= pv
        
        for row in range(n):
            if row == col: continue
            factor = M[row][col]
            for j in range(2 * n):
                M[row][j] -= factor * M[col][j]
    return [row[n:] for row in M]

def mat_solve(A, b):
    """Solve A x = b via matrix inverse (simple, not optimized).""""
    A_inv = mat_inv(A)
    return mat_vec(A_inv, b)

def mat_transpose(A):
    m, n = len(A), len(A[0]) if A else 0
    return [[A[i][j] for i in range(m)] for j in range(n)]

def mat_outer3(G, v):
    """3-tensor contraction: result[i, k] = Σ_j G[i, j, k] * v[j]""""
    d1 = len(G); d2 = len(G[0]) if G[0] else 0; d3 = len(G[0][0]) if G[0] and G[0][0] else 0
    result = mat_zero(d1, d3)
    for i in range(d1):
        for k in range(d3):
            s = 0.0
            for j in range(d2):
                s += G[i][j][k] * v[j]
            result[i][k] = s
    return result






class DistributionFamily(ABC):
    @abstractmethod
    def log_prob(self, x, theta) -> float: ...
    @abstractmethod
    def score(self, x, theta) -> List[float]: ...
    @abstractmethod
    def sample(self, theta, n=1, rng=None): ...
    @abstractmethod
    def dim(self) -> int: ...


class Bernoulli(DistributionFamily):
    def log_prob(self, x, theta):
        p = float(theta[0])
        x = int(x)
        if x == 1: return math.log(max(p, 1e-12))
        return math.log(max(1 - p, 1e-12))

    def score(self, x, theta):
        p = float(theta[0])
        x = int(x)
        return [(x - p) / (p * (1 - p) + 1e-12)]

    def sample(self, theta, n=1, rng=None):
        if rng is None: rng = random
        p = float(theta[0])
        return [1 if rng.random() < p else 0 for _ in range(n)]

    def dim(self): return 1


class Gaussian(DistributionFamily):
    def log_prob(self, x, theta):
        mu, sigma = float(theta[0]), float(theta[1])
        if sigma <= 0: return float('-inf')
        return -0.5 * math.log(2 * math.pi) - math.log(sigma) - 0.5 * ((x - mu) / sigma) ** 2

    def score(self, x, theta):
        mu, sigma = float(theta[0]), float(theta[1])
        v = x - mu
        dmu = v / (sigma * sigma + 1e-12)
        dsigma = (v * v - sigma * sigma) / (sigma ** 3 + 1e-12)
        return [dmu, dsigma]

    def sample(self, theta, n=1, rng=None):
        if rng is None: rng = random
        mu, sigma = float(theta[0]), float(theta[1])
        return [rng.gauss(mu, sigma) for _ in range(n)]

    def dim(self): return 2


class Categorical(DistributionFamily):
    def __init__(self, k: int):
        self.k = k

    def log_prob(self, x, theta):
        return math.log(max(theta[int(x)], 1e-12))

    def score(self, x, theta):
        x = int(x)
        return [1.0 / (theta[j] + 1e-12) - 1.0 if j == x else -1.0
                for j in range(self.k)]

    def sample(self, theta, n=1, rng=None):
        if rng is None: rng = random
        theta = list(theta) / sum(theta) if hasattr(theta, "__truediv__") else [t / sum(theta) for t in theta]
        
        cum = []
        s = 0.0
        for t in theta:
            s += t
            cum.append(s)
        result = []
        for _ in range(n):
            r = rng.random()
            for i, c in enumerate(cum):
                if r <= c:
                    result.append(i)
                    break
        return result

    def dim(self): return self.k






@dataclass
class StatisticalManifold:
    family: DistributionFamily
    n_samples: int = 1000
    metric: str = "fisher"

    def fisher_information(self, theta, x_samples=None):
        theta = list(theta) if theta else []
        d = self.family.dim()
        if x_samples is None:
            x_samples = self.family.sample(theta, self.n_samples)
        g = mat_zero(d, d)
        for x in x_samples:
            s = self.family.score(x, theta)
            for i in range(d):
                for j in range(d):
                    g[i][j] += s[i] * s[j]
        return mat_scale(g, 1.0 / max(len(x_samples), 1))

    def inner_product(self, u, v, theta, x_samples=None):
        g = self.fisher_information(theta, x_samples)
        return vec_dot(mat_vec(g, u), v)

    def norm(self, v, theta):
        return math.sqrt(max(0, self.inner_product(v, v, theta)))

    def distance(self, theta1, theta2):
        n_steps = 50
        dt = 1.0 / n_steps
        theta1 = list(theta1); theta2 = list(theta2)
        total = 0.0
        for s in range(n_steps):
            t = s / n_steps
            theta_mid = [theta1[i] * (1 - t) + theta2[i] * t for i in range(len(theta1))]
            dtheta = [(theta2[i] - theta1[i]) * dt for i in range(len(theta1))]
            total += self.norm(dtheta, theta_mid)
        return total


class ExponentialFamily(DistributionFamily):
    """Exponential family in canonical (natural) parameterization.

    P_θ(x) = exp(θ · T(x) - A(θ)) · h(x)
    """"
    def __init__(self, sufficient_stats: Callable, log_base: Callable = lambda x: 0.0,
                 sample_fn: Optional[Callable] = None):
        self.T = sufficient_stats
        self.log_h = log_base
        self._sample_fn = sample_fn

    def log_A(self, theta) -> float:
        if self._sample_fn is None:
            raise NotImplementedError("Provide closed form for A or sample_fn")
        theta = list(theta) if not isinstance(theta, list) else theta
        n = 1000
        samples = self._sample_fn(n)
        log_terms = [float(sum(theta[k] * self.T(s)[k] for k in range(len(theta))))
                     + self.log_h(s) for s in samples]
        if not log_terms: return float('-inf')
        max_lt = max(log_terms)
        return max_lt + math.log(sum(math.exp(lt - max_lt) for lt in log_terms) / n)

    def log_prob(self, x, theta):
        theta = list(theta)
        return float(sum(theta[k] * self.T(x)[k] for k in range(len(theta)))) - self.log_A(theta) + self.log_h(x)

    def score(self, x, theta):
        theta = list(theta)
        T_x = self.T(x)
        grad_A = self.gradient_A(theta)
        return [T_x[i] - grad_A[i] for i in range(len(theta))]

    def sample(self, theta, n=1, rng=None):
        if self._sample_fn is None: raise NotImplementedError
        return self._sample_fn(n)

    def gradient_A(self, theta) -> List[float]:
        theta = list(theta); d = len(theta)
        eps = 1e-5
        grad = [0.0] * d
        for i in range(d):
            tp = list(theta); tp[i] += eps
            tm = list(theta); tm[i] -= eps
            grad[i] = (self.log_A(tp) - self.log_A(tm)) / (2 * eps)
        return grad

    def hessian_A(self, theta) -> List[List[float]]:
        theta = list(theta); d = len(theta)
        eps = 1e-4
        H = mat_zero(d, d)
        for i in range(d):
            for j in range(d):
                tpp = list(theta); tpp[i] += eps; tpp[j] += eps
                tpm = list(theta); tpm[i] += eps; tpm[j] -= eps
                tmp = list(theta); tmp[i] -= eps; tmp[j] += eps
                tmm = list(theta); tmm[i] -= eps; tmm[j] -= eps
                H[i][j] = (self.log_A(tpp) - self.log_A(tpm) - self.log_A(tmp) + self.log_A(tmm)) / (4 * eps * eps)
        return H

    def dim(self):
        if self._sample_fn is None: return 0
        sample = self._sample_fn(1)
        return len(self.T(sample[0]))


class MixtureFamily(DistributionFamily):
    def __init__(self, components: List[DistributionFamily]):
        self.components = components

    def log_prob(self, x, theta):
        theta = list(theta)
        return math.log(sum(theta[i] * math.exp(self.components[i].log_prob(x, [0]))
                            for i in range(len(self.components))) + 1e-12)

    def score(self, x, theta):
        d = len(theta)
        eps = 1e-5
        grad = [0.0] * d
        for i in range(d):
            tp = list(theta); tp[i] += eps
            tm = list(theta); tm[i] -= eps
            grad[i] = (self.log_prob(x, tp) - self.log_prob(x, tm)) / (2 * eps)
        return grad

    def sample(self, theta, n=1, rng=None):
        if rng is None: rng = random
        total = sum(theta)
        theta_n = [t / total for t in theta]
        cum = []; s = 0.0
        for t in theta_n:
            s += t
            cum.append(s)
        return [self.components[next(i for i, c in enumerate(cum) if r <= c)].sample([0], 1, rng)[0]
                for r in (rng.random() for _ in range(n))]

    def dim(self): return len(self.components)
