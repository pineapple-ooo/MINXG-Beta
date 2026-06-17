"""
minxg/chaos/bifurcation.py — Bifurcation Diagrams
=========================================================

A BIFURCATION DIAGRAM plots the long-term behavior of a dynamical system
as a function of a parameter. The most famous: the LOGISTIC MAP bifurcation
diagram showing period-doubling route to chaos at r ≈ 3.5699.
"""
from __future__ import annotations
from typing import Callable, List, Tuple


def bifurcation_diagram(map_fn: Callable[[float, float], float],
                         param_range: Tuple[float, float],
                         n_params: int = 1000,
                         transient: int = 1000,
                         plot_points: int = 200,
                         x_range: Tuple[float, float] = (0, 1)) -> List[Tuple[float, float]]:
    """Compute a bifurcation diagram.

    Args:
        map_fn: f(x, r) - the map takes state x and parameter r
        param_range: (r_min, r_max) to sweep
        n_params: number of parameter values
        transient: iterations to discard (let trajectory settle)
        plot_points: iterations to plot after transient
        x_range: range of x to include (filters out transients in some maps)

    Returns:
        List of (r, x) points to plot.
    """
    r_min, r_max = param_range
    dr = (r_max - r_min) / max(n_params - 1, 1)
    out = []
    for i in range(n_params):
        r = r_min + i * dr
        
        x = 0.5
        
        for _ in range(transient):
            x = map_fn(x, r)
            
            if abs(x) > 1e10: break
        
        for _ in range(plot_points):
            x = map_fn(x, r)
            if abs(x) > 1e10:
                x = float('nan')
            elif x_range[0] <= x <= x_range[1]:
                out.append((r, x))
    return out


def logistic_bifurcation(r_min: float = 2.5, r_max: float = 4.0,
                          n_params: int = 500) -> List[Tuple[float, float]]:
    """The classic logistic map bifurcation diagram."""
    return bifurcation_diagram(
        map_fn=lambda x, r: r * x * (1 - x),
        param_range=(r_min, r_max),
        n_params=n_params,
        transient=500,
        plot_points=100,
    )


def feigenbaum_constant():
    """The Feigenbaum constant δ ≈ 4.6692016... — universal ratio of period-doubling bifurcations."""
    return 4.66920160910299067185320382046620161725818557747576863274
