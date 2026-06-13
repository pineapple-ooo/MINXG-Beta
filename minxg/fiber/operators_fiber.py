"""
minxg/fiber/operators_fiber.py — Register Fiber Bundle operators
==========================================================================

50+ fiber bundle operators. Operator IDs 6000-6499 are reserved.
"""
from __future__ import annotations
import math
from typing import Any, Callable, Dict, List, Optional, Tuple
from ..operators import Operator, OPERATOR_REGISTRY
from .bundle import FiberBundle, VectorBundle, PrincipalBundle
from .connection import Connection, ParallelTransport, Curvature
from .section import Section, CovariantDerivative
from .tangent import TangentBundle, RiemannianMetric
from .frame import FrameBundle, Vielbein, vielbein


def register_fiber_operators():
    reg = OPERATOR_REGISTRY
    op_id = 6000

    
    def make_vector_bundle(base_dim, fiber_dim):
        return VectorBundle(int(base_dim), int(fiber_dim))
    reg.register(Operator(op_id, "fiber_vector_bundle", "fiber",
                          "Construct a vector bundle (fiber = R^n)",
                          ["int", "int"], "bundle", True, make_vector_bundle)); op_id += 1

    def make_principal_bundle(base_dim, group_dim, group_name):
        return PrincipalBundle(int(base_dim), int(group_dim), str(group_name))
    reg.register(Operator(op_id, "fiber_principal_bundle", "fiber",
                          "Construct a principal G-bundle",
                          ["int", "int", "string"], "bundle", True, make_principal_bundle)); op_id += 1

    def make_tangent_bundle(dim, metric_fn_str):
        """Build a tangent bundle with a string-defined metric function."""
        metric_callable = eval("lambda p: " + metric_fn_str) if isinstance(metric_fn_str, str) else metric_fn_str
        return TangentBundle(int(dim), RiemannianMetric(metric_callable))
    reg.register(Operator(op_id, "fiber_tangent_bundle", "fiber",
                          "Tangent bundle T(M) with metric",
                          ["int", "string"], "bundle", True, make_tangent_bundle)); op_id += 1

    
    for name, fn in [
        ("fiber_metric_euclidean_2", lambda p: [[1, 0], [0, 1]]),
        ("fiber_metric_euclidean_3", lambda p: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
        ("fiber_metric_sphere_2", lambda p: [[1, 0], [0, math.sin(p[0]) ** 2]]),
        ("fiber_metric_hyperbolic_2", lambda p: [[1, 0], [0, math.cosh(p[0]) ** 2]]),
        ("fiber_metric_minkowski_2", lambda p: [[-1, 0], [0, 1]]),
    ]:
        reg.register(Operator(op_id, name, "fiber",
                              f"Standard {name[14:]} metric",
                              [], "metric", True, fn))
        op_id += 1

    
    def make_connection(dim):
        return Connection(int(dim))
    reg.register(Operator(op_id, "fiber_connection", "fiber",
                          "Trivial (zero) connection on a vector bundle",
                          ["int"], "connection", True, make_connection)); op_id += 1

    def make_connection_levi_civita(dim, metric_fn_str):
        """Levi-Civita connection from a metric (Christoffel symbols)."""
        metric_callable = eval("lambda p: " + metric_fn_str) if isinstance(metric_fn_str, str) else metric_fn_str
        metric = RiemannianMetric(metric_callable)
        tb = TangentBundle(int(dim), metric)
        
        def lc_fn(point):
            return tb.levi_civita(point)
        return Connection(int(dim), lc_fn)
    reg.register(Operator(op_id, "fiber_connection_levi_civita", "fiber",
                          "Levi-Civita connection (torsion-free, metric-compatible)",
                          ["int", "string"], "connection", True, make_connection_levi_civita)); op_id += 1

    def christoffel_at(conn, point):
        return conn.christoffel(list(point))
    reg.register(Operator(op_id, "fiber_christoffel", "fiber",
                          "Christoffel symbols Γ^i_jk at a point",
                          ["connection", "array"], "tensor3", True, christoffel_at)); op_id += 1

    
    def make_pt(conn, curve_fn_str, t_min, t_max):
        curve = eval("lambda t: " + curve_fn_str) if isinstance(curve_fn_str, str) else curve_fn_str
        return ParallelTransport(conn, curve, float(t_min), float(t_max))
    reg.register(Operator(op_id, "fiber_parallel_transport", "fiber",
                          "Parallel transport along a curve",
                          ["connection", "string", "number", "number"],
                          "transport", True, make_pt)); op_id += 1

    def pt_transport(pt, initial, n_steps):
        return pt.transport(list(initial), int(n_steps))
    reg.register(Operator(op_id, "fiber_pt_transport", "fiber",
                          "Transport a vector along the curve",
                          ["transport", "array", "int"], "array", True, pt_transport)); op_id += 1

    def pt_holonomy(pt, initial, n_steps):
        return pt.holonomy(list(initial), int(n_steps))
    reg.register(Operator(op_id, "fiber_holonomy", "fiber",
                          "Holonomy: parallel transport around a closed loop",
                          ["transport", "array", "int"], "array", True, pt_holonomy)); op_id += 1

    
    def make_curvature(conn):
        return Curvature(conn)
    reg.register(Operator(op_id, "fiber_curvature", "fiber",
                          "Curvature 2-form F of a connection",
                          ["connection"], "curvature", True, make_curvature)); op_id += 1

    def riemann_at(curv, point):
        return curv.riemann_tensor(list(point))
    reg.register(Operator(op_id, "fiber_riemann_tensor", "fiber",
                          "Riemann curvature tensor R^i_jkl at a point",
                          ["curvature", "array"], "tensor4", True, riemann_at)); op_id += 1

    def ricci_at(curv, point):
        return curv.ricci_tensor(list(point))
    reg.register(Operator(op_id, "fiber_ricci_tensor", "fiber",
                          "Ricci tensor R_jl = R^i_jil",
                          ["curvature", "array"], "matrix", True, ricci_at)); op_id += 1

    def scalar_curvature_at(curv, point, metric):
        return curv.scalar_curvature(list(point), metric.at(list(point)))
    reg.register(Operator(op_id, "fiber_scalar_curvature", "fiber",
                          "Scalar curvature R = g^jl R_jl",
                          ["curvature", "array", "metric"], "number", True, scalar_curvature_at)); op_id += 1

    
    def make_section(section_fn_str, fiber_dim):
        fn = eval("lambda p: " + section_fn_str) if isinstance(section_fn_str, str) else section_fn_str
        return Section(fn, int(fiber_dim))
    reg.register(Operator(op_id, "fiber_section", "fiber",
                          "Construct a section from a function",
                          ["string", "int"], "section", True, make_section)); op_id += 1

    def section_at(sec, point):
        return sec(list(point))
    reg.register(Operator(op_id, "fiber_section_at", "fiber",
                          "Evaluate a section at a point",
                          ["section", "array"], "array", True, section_at)); op_id += 1

    def make_cov_deriv(conn):
        return CovariantDerivative(conn)
    reg.register(Operator(op_id, "fiber_covariant_derivative", "fiber",
                          "Covariant derivative D_i s = ∂_i s + Γ·s",
                          ["connection"], "cov_deriv", True, make_cov_deriv)); op_id += 1

    def cov_deriv_apply(cd, sec, point, direction):
        return cd.apply(sec, list(point), int(direction))
    reg.register(Operator(op_id, "fiber_cov_deriv_apply", "fiber",
                          "Apply covariant derivative in a direction",
                          ["cov_deriv", "section", "array", "int"],
                          "array", True, cov_deriv_apply)); op_id += 1

    def divergence(cd, sec, point):
        return cd.divergence(sec, list(point))
    reg.register(Operator(op_id, "fiber_divergence", "fiber",
                          "Divergence of a vector section",
                          ["cov_deriv", "section", "array"], "number", True, divergence)); op_id += 1

    def laplacian(cd, sec, point):
        return cd.laplacian(sec, list(point))
    reg.register(Operator(op_id, "fiber_laplacian", "fiber",
                          "Covariant Laplacian Δ s = Σ_i D_i D_i s",
                          ["cov_deriv", "section", "array"], "array", True, laplacian)); op_id += 1

    
    def geodesic(tb, point, velocity, t_max, n_steps):
        return tb.geodesic(list(point), list(velocity), float(t_max), int(n_steps))
    reg.register(Operator(op_id, "fiber_geodesic", "fiber",
                          "Compute a geodesic (shortest path) on the manifold",
                          ["bundle", "array", "array", "number", "int"],
                          "list", True, geodesic)); op_id += 1

    def exp_map(tb, point, velocity, t, n_steps):
        return tb.exponential_map(list(point), list(velocity), float(t), int(n_steps))
    reg.register(Operator(op_id, "fiber_exp_map", "fiber",
                          "Exponential map: exp_p(t·v)",
                          ["bundle", "array", "array", "number", "int"],
                          "array", True, exp_map)); op_id += 1

    def levi_civita(tb, point):
        return tb.levi_civita(list(point))
    reg.register(Operator(op_id, "fiber_levi_civita", "fiber",
                          "Levi-Civita Christoffel symbols at a point",
                          ["bundle", "array"], "tensor3", True, levi_civita)); op_id += 1

    
    def make_frame_bundle(base_dim, group):
        return FrameBundle(int(base_dim), str(group))
    reg.register(Operator(op_id, "fiber_frame_bundle", "fiber",
                          "Frame bundle F(M) — principal GL(n) or SO(n) bundle",
                          ["int", "string"], "frame_bundle", True, make_frame_bundle)); op_id += 1

    def make_vielbein(point, metric):
        return vielbein(list(point), metric)
    reg.register(Operator(op_id, "fiber_vielbein", "fiber",
                          "Construct a vielbein (orthonormal frame) at a point",
                          ["array", "metric"], "vielbein", True, make_vielbein)); op_id += 1

    def vielbein_at(v, point):
        return v.at(list(point))
    reg.register(Operator(op_id, "fiber_vielbein_at", "fiber",
                          "Vielbein matrix e^a_μ at a point",
                          ["vielbein", "array"], "matrix", True, vielbein_at)); op_id += 1

    def vielbein_inverse(v, point):
        return v.inverse(list(point))
    reg.register(Operator(op_id, "fiber_vielbein_inverse", "fiber",
                          "Inverse vielbein e^μ_a",
                          ["vielbein", "array"], "matrix", True, vielbein_inverse)); op_id += 1

    
    def metric_at(m, point):
        return m.at(list(point))
    reg.register(Operator(op_id, "fiber_metric_at", "fiber",
                          "Metric tensor g_ij at a point",
                          ["metric", "array"], "matrix", True, metric_at)); op_id += 1

    def metric_inner(m, u, v, point):
        return m.inner(list(u), list(v), list(point))
    reg.register(Operator(op_id, "fiber_metric_inner", "fiber",
                          "Inner product <u, v>_g = u^T g v",
                          ["metric", "array", "array", "array"], "number", True, metric_inner)); op_id += 1

    def metric_norm(m, v, point):
        return m.norm(list(v), list(point))
    reg.register(Operator(op_id, "fiber_metric_norm", "fiber",
                          "Riemannian norm |v|_g",
                          ["metric", "array", "array"], "number", True, metric_norm)); op_id += 1

    
    def sphere_n(n):
        """S^n as a Riemannian manifold."""
        dim = int(n) + 1
        
        return TangentBundle(int(n), RiemannianMetric(
            lambda p: [[1.0 if i == j else 0.0 for j in range(int(n))] for i in range(int(n))]
        ))
    for k in [1, 2, 3, 4, 5]:
        reg.register(Operator(op_id, f"fiber_sphere_{k}", "fiber",
                              f"S^{k} as a Riemannian manifold",
                              [], "manifold", True, lambda k=k: sphere_n(k)))
        op_id += 1

    def hyperbolic_n(n):
        """H^n as a Riemannian manifold (hyperboloid model)."""
        dim = int(n)
        return TangentBundle(dim, RiemannianMetric(
            lambda p: [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]
        ))
    for k in [2, 3, 4]:
        reg.register(Operator(op_id, f"fiber_hyperbolic_{k}", "fiber",
                              f"H^{k} (hyperbolic space)",
                              [], "manifold", True, lambda k=k: hyperbolic_n(k)))
        op_id += 1

    def euclidean_n(n):
        return TangentBundle(int(n), RiemannianMetric(
            lambda p: [[1.0 if i == j else 0.0 for j in range(int(n))] for i in range(int(n))]
        ))
    for k in [1, 2, 3, 4, 5, 6, 7, 8]:
        reg.register(Operator(op_id, f"fiber_euclidean_{k}", "fiber",
                              f"Euclidean R^{k} (flat manifold)",
                              [], "manifold", True, lambda k=k: euclidean_n(k)))
        op_id += 1

    def minkowski_n(n):
        return TangentBundle(int(n), RiemannianMetric(
            lambda p: [[-1.0 if i == 0 and j == 0 else (1.0 if i == j else 0.0) for j in range(int(n))] for i in range(int(n))]
        ))
    for k in [2, 3, 4]:
        reg.register(Operator(op_id, f"fiber_minkowski_{k}", "fiber",
                              f"Minkowski R^{k} (spacetime, signature (-,+,...,+))",
                              [], "manifold", True, lambda k=k: minkowski_n(k)))
        op_id += 1

    return op_id - 6000


FIBER_OPERATOR_COUNT = register_fiber_operators()
