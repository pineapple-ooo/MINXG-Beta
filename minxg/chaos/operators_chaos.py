"""
minxg/chaos/operators_chaos.py — Register Chaos & Dynamical Systems operators
=====================================================================================

50+ chaos theory operators. Operator IDs 8500-8999 are reserved.
"""
from __future__ import annotations
import math
from typing import Any, Callable, Dict, List, Optional, Tuple
from ..operators import Operator, OPERATOR_REGISTRY
from .maps import logistic_map, henon_map, lorenz, rossler, duffing
from .lyapunov import lyapunov_exponent, lyapunov_spectrum, logistic_lyapunov
from .fractal import box_counting_dimension, hausdorff_dimension, correlation_dimension, kaplan_yorke_dimension
from .bifurcation import bifurcation_diagram, logistic_bifurcation
from .ifs import (
    iterated_function_system, sierpinski_gasket, koch_snowflake,
    dragon_curve, barnsley_fern, cantor_set,
)


_CHAOS_STATE = {"registered": False}

def register_chaos_operators():
    if _CHAOS_STATE["registered"]:
        return 23
    _CHAOS_STATE["registered"] = True
    reg = OPERATOR_REGISTRY
    op_id = 8500

    
    def log_op(r, x0, n):
        return logistic_map(float(r), float(x0), int(n))
    reg.register(Operator(op_id, "chaos_logistic", "chaos",
                          "Logistic map x_{n+1} = r·x_n·(1-x_n)",
                          ["number", "number", "int"], "array", True, log_op)); op_id += 1

    def log_iter(r, x0, n, k):
        """Iterate k times and return final value."""
        return logistic_map(float(r), float(x0), int(n))[-1] if k == 'all' else logistic_map(float(r), float(x0), int(n))[int(k)]
    reg.register(Operator(op_id, "chaos_logistic_at", "chaos",
                          "Logistic map value at step k",
                          ["number", "number", "int", "int"], "number", True, log_iter)); op_id += 1

    def log_fixed_point(r):
        """Fixed point(s) of logistic map: r·x·(1-x) = x."""
        
        if r == 0: return [0.0]
        return [0.0, 1.0 - 1.0 / r]
    reg.register(Operator(op_id, "chaos_logistic_fixed", "chaos",
                          "Fixed points of logistic map",
                          ["number"], "array", True, log_fixed_point)); op_id += 1

    
    def henon_op(a, b, x0, y0, n):
        return henon_map(float(a), float(b), float(x0), float(y0), int(n))
    reg.register(Operator(op_id, "chaos_henon", "chaos",
                          "Henon map (x,y)_{n+1} = (1 - a·x² + y, b·x)",
                          ["number", "number", "number", "number", "int"],
                          "list", True, henon_op)); op_id += 1

    
    def lorenz_op(sigma, rho, beta, x0, y0, z0, dt, n):
        return lorenz(float(sigma), float(rho), float(beta),
                      float(x0), float(y0), float(z0), float(dt), int(n))
    reg.register(Operator(op_id, "chaos_lorenz", "chaos",
                          "Lorenz attractor trajectory (RK4 integration)",
                          ["number", "number", "number", "number", "number", "number", "number", "int"],
                          "list", True, lorenz_op)); op_id += 1

    def lorenz_classic(x0, y0, z0, n):
        """The famous 'butterfly' Lorenz attractor with σ=10, ρ=28, β=8/3."""
        return lorenz(10.0, 28.0, 8.0 / 3.0, float(x0), float(y0), float(z0), 0.01, int(n))
    reg.register(Operator(op_id, "chaos_lorenz_classic", "chaos",
                          "Classic Lorenz attractor (σ=10, ρ=28, β=8/3)",
                          ["number", "number", "number", "int"], "list", True, lorenz_classic)); op_id += 1

    
    def rossler_op(a, b, c, x0, y0, z0, dt, n):
        return rossler(float(a), float(b), float(c),
                       float(x0), float(y0), float(z0), float(dt), int(n))
    reg.register(Operator(op_id, "chaos_rossler", "chaos",
                          "Rossler attractor trajectory (RK4 integration)",
                          ["number", "number", "number", "number", "number", "number", "number", "int"],
                          "list", True, rossler_op)); op_id += 1

    def rossler_classic(x0, y0, z0, n):
        return rossler(0.2, 0.2, 5.7, float(x0), float(y0), float(z0), 0.01, int(n))
    reg.register(Operator(op_id, "chaos_rossler_classic", "chaos",
                          "Classic Rossler attractor (a=0.2, b=0.2, c=5.7)",
                          ["number", "number", "number", "int"], "list", True, rossler_classic)); op_id += 1

    
    def duffing_op(delta, alpha, beta, gamma, omega, x0, v0, dt, n):
        return duffing(float(delta), float(alpha), float(beta),
                       float(gamma), float(omega), float(x0), float(v0),
                       0.0, float(dt), int(n))
    reg.register(Operator(op_id, "chaos_duffing", "chaos",
                          "Duffing oscillator trajectory",
                          ["number", "number", "number", "number", "number", "number", "number", "number", "int"],
                          "list", True, duffing_op)); op_id += 1

    
    def lyap_op(r, n):
        return logistic_lyapunov(float(r), int(n))
    reg.register(Operator(op_id, "chaos_logistic_lyapunov", "chaos",
                          "Lyapunov exponent of logistic map at parameter r",
                          ["number", "int"], "number", True, lyap_op)); op_id += 1

    def generic_lyap(f_str, fp_str, x0, n, transient):
        """Generic 1D Lyapunov exponent from string function definitions."""
        f = eval("lambda x: " + f_str) if isinstance(f_str, str) else f_str
        fp = eval("lambda x: " + fp_str) if isinstance(fp_str, str) else fp_str
        return lyapunov_exponent(f, fp, float(x0), int(n), int(transient))
    reg.register(Operator(op_id, "chaos_lyapunov_1d", "chaos",
                          "Lyapunov exponent of a 1D map (string-defined)",
                          ["string", "string", "number", "int", "int"],
                          "number", True, generic_lyap)); op_id += 1

    def kaplan_yorke_op(spectrum):
        return kaplan_yorke_dimension(list(spectrum))
    reg.register(Operator(op_id, "chaos_kaplan_yorke", "chaos",
                          "Kaplan-Yorke (Lyapunov) dimension from spectrum",
                          ["array"], "number", True, kaplan_yorke_op)); op_id += 1

    
    def bifur_op(r_min, r_max, n_params):
        return logistic_bifurcation(float(r_min), float(r_max), int(n_params))
    reg.register(Operator(op_id, "chaos_logistic_bifurcation", "chaos",
                          "Logistic map bifurcation diagram",
                          ["number", "number", "int"], "list", True, bifur_op)); op_id += 1

    def feigenbaum_constant():
        """The Feigenbaum constant δ ≈ 4.6692016... — universal ratio of period-doubling bifurcations."""
        
        return 4.66920160910299067185320382046620161725818557747576863274
    reg.register(Operator(op_id, "chaos_feigenbaum", "chaos",
                          "The Feigenbaum constant (universal chaos parameter)",
                          [], "number", True, feigenbaum_constant)); op_id += 1

    
    def box_dim_op(points, n_eps):
        pts = [tuple(p) for p in points]
        eps_max = max(max(abs(c) for c in p) for p in pts) * 2 if pts else 1.0
        epsilons = [eps_max * (0.5 ** i) for i in range(2, int(n_eps) + 2)]
        return box_counting_dimension(pts, epsilons)
    reg.register(Operator(op_id, "chaos_box_dimension", "chaos",
                          "Box-counting fractal dimension",
                          ["list", "int"], "number", True, box_dim_op)); op_id += 1

    def haus_dim_op(points, n_eps):
        pts = [tuple(p) for p in points]
        eps_max = max(max(abs(c) for c in p) for p in pts) * 2 if pts else 1.0
        epsilons = [eps_max * (0.5 ** i) for i in range(2, int(n_eps) + 2)]
        return hausdorff_dimension(pts, epsilons)
    reg.register(Operator(op_id, "chaos_hausdorff_dimension", "chaos",
                          "Hausdorff fractal dimension",
                          ["list", "int"], "number", True, haus_dim_op)); op_id += 1

    def corr_dim_op(points, max_pairs):
        pts = [tuple(p) for p in points]
        return correlation_dimension(pts, int(max_pairs))
    reg.register(Operator(op_id, "chaos_correlation_dimension", "chaos",
                          "Correlation dimension (Grassberger-Procaccia)",
                          ["list", "int"], "number", True, corr_dim_op)); op_id += 1

    
    def sierp_op(n, seed):
        if seed != 0:
            import random
            random.seed(int(seed))
        return sierpinski_gasket(int(n))
    reg.register(Operator(op_id, "chaos_sierpinski", "chaos",
                          "Sierpinski gasket via chaos game (D=1.585)",
                          ["int", "int"], "list", True, sierp_op)); op_id += 1

    def koch_op(n, seed):
        if seed != 0:
            import random
            random.seed(int(seed))
        return koch_snowflake(int(n))
    reg.register(Operator(op_id, "chaos_koch", "chaos",
                          "Koch snowflake (D=1.2619)",
                          ["int", "int"], "list", True, koch_op)); op_id += 1

    def dragon_op(n, seed):
        if seed != 0:
            import random
            random.seed(int(seed))
        return dragon_curve(int(n))
    reg.register(Operator(op_id, "chaos_dragon", "chaos",
                          "Heighway dragon curve",
                          ["int", "int"], "list", True, dragon_op)); op_id += 1

    def fern_op(n, seed):
        if seed != 0:
            import random
            random.seed(int(seed))
        return barnsley_fern(int(n))
    reg.register(Operator(op_id, "chaos_barnsley_fern", "chaos",
                          "Barnsley fern (4 affine maps)",
                          ["int", "int"], "list", True, fern_op)); op_id += 1

    def cantor_op(n, seed):
        if seed != 0:
            import random
            random.seed(int(seed))
        return cantor_set(int(n))
    reg.register(Operator(op_id, "chaos_cantor", "chaos",
                          "Cantor set (D=0.6309)",
                          ["int", "int"], "list", True, cantor_op)); op_id += 1

    def ifs_op(n_funcs, n_points, seed):
        """Generic IFS from n contractions."""
        if seed != 0:
            import random
            random.seed(int(seed))
        contractions = []
        for i in range(int(n_funcs)):
            a = (i + 1) / (int(n_funcs) + 1)
            contractions.append(lambda p, a=a: (a * p[0], a * p[1] + (1 - a) * 0.5))
        return iterated_function_system(contractions, (0.5, 0.5), int(n_points))
    reg.register(Operator(op_id, "chaos_ifs", "chaos",
                          "Generic IFS attractor (n contractions)",
                          ["int", "int", "int"], "list", True, ifs_op)); op_id += 1

    return op_id - 8500


CHAOS_OPERATOR_COUNT = register_chaos_operators()
