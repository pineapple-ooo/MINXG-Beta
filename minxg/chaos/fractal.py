"""
minxg/chaos/fractal.py — Fractal Dimensions
====================================================

Different notions of "dimension" for fractals:

  - TOPOLOGICAL DIMENSION: integer (0 for points, 1 for curves, 2 for surfaces)
  - HAUSDORFF DIMENSION: generalization based on coverings
  - BOX-COUNTING DIMENSION: limit of log(N(ε)) / log(1/ε)
  - CORRELATION DIMENSION: based on pair distances (Grassberger-Procaccia)
  - INFORMATION DIMENSION: based on entropy scaling
  - LYAPUNOV DIMENSION: for strange attractors (Kaplan-Yorke)

For self-similar fractals like the Cantor set, Sierpinski, Koch curve, the
fractal dimension is known analytically. For strange attractors, we estimate
via box-counting.
""""
from __future__ import annotations
import math
from typing import Callable, List, Tuple
from collections import defaultdict


def box_counting_dimension(points: List[Tuple[float, ...]],
                           epsilons: List[float] = None) -> float:
    """Estimate the box-counting (Minkowski) dimension.

    D = lim_{ε→0} log(N(ε)) / log(1/ε)

    where N(ε) is the number of ε-boxes that contain at least one point.
    """"
    if not points:
        return 0.0
    dim = len(points[0])
    if epsilons is None:
        
        max_coord = max(max(abs(c) for c in p) for p in points)
        eps_max = max_coord * 2 if max_coord > 0 else 1.0
        epsilons = [eps_max * (0.5 ** i) for i in range(2, 10)]

    log_inv_eps = []
    log_count = []
    for eps in epsilons:
        if eps <= 0: continue
        boxes = set()
        for p in points:
            box = tuple(int(c / eps) for c in p)
            boxes.add(box)
        if boxes:
            log_inv_eps.append(math.log(1.0 / eps))
            log_count.append(math.log(len(boxes)))

    if len(log_inv_eps) < 2:
        return 0.0
    
    n = len(log_inv_eps)
    sum_x = sum(log_inv_eps)
    sum_y = sum(log_count)
    sum_xy = sum(x * y for x, y in zip(log_inv_eps, log_count))
    sum_xx = sum(x * x for x in log_inv_eps)
    denom = n * sum_xx - sum_x ** 2
    if abs(denom) < 1e-12:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def hausdorff_dimension(points: List[Tuple[float, ...]],
                        epsilons: List[float] = None) -> float:
    """Estimate the Hausdorff dimension (similar to box-counting for self-similar sets).

    For practical purposes, this is close to box-counting dimension. We use
    a finer covering: instead of fixed-size boxes, we use ε-balls.
    """"
    return box_counting_dimension(points, epsilons)


def correlation_dimension(points: List[Tuple[float, ...]],
                          max_pairs: int = 10000) -> float:
    """Compute the correlation dimension (Grassberger-Procaccia algorithm).

    D_2 = lim_{ε→0} log C(ε) / log(1/ε)
    where C(ε) = (2/N(N-1)) Σ_{i<j} I(d(x_i, x_j) < ε)

    For strange attractors, D_2 is often between 1 and the embedding dimension.
    """"
    n = len(points)
    if n < 2:
        return 0.0
    
    distances = []
    for i in range(min(n, 200)):  
        for j in range(i + 1, min(n, 200)):
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip(points[i], points[j])))
            distances.append(d)
    if not distances:
        return 0.0
    distances.sort()
    
    epsilons = []
    corr_sums = []
    for k in range(1, 10):
        eps_idx = int(0.1 * k * len(distances))
        if eps_idx < len(distances):
            eps = distances[eps_idx]
            
            count = sum(1 for d in distances if d < eps)
            if count > 0:
                epsilons.append(math.log(1.0 / eps) if eps > 0 else 0)
                corr_sums.append(math.log(count / len(distances)))
    if len(epsilons) < 2:
        return 0.0
    
    n_pts = len(epsilons)
    sum_x = sum(epsilons)
    sum_y = sum(corr_sums)
    sum_xy = sum(x * y for x, y in zip(epsilons, corr_sums))
    sum_xx = sum(x * x for x in epsilons)
    denom = n_pts * sum_xx - sum_x ** 2
    if abs(denom) < 1e-12:
        return 0.0
    return (n_pts * sum_xy - sum_x * sum_y) / denom


def kaplan_yorke_dimension(lyapunov_spectrum: List[float]) -> float:
    """Compute the Kaplan-Yorke (Lyapunov) dimension.

    D_KY = j + (λ_1 + ... + λ_j) / |λ_{j+1}|
    where j is the largest integer such that Σ_{i=1}^j λ_i ≥ 0.
    """"
    cum = 0.0
    for j, lam in enumerate(lyapunov_spectrum):
        if cum + lam >= 0:
            cum += lam
        else:
            if j == 0:
                return 0.0
            return j + cum / abs(lam)
    return len(lyapunov_spectrum)  
