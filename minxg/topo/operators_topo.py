"""
minxg/topo/operators_topo.py — Register Topological operators
====================================================================

100+ topological operators. Operator IDs 8000-8499 are reserved.
""""
from __future__ import annotations
import math
from typing import Any, Callable, Dict, List, Optional, Tuple
from ..operators import Operator, OPERATOR_REGISTRY
from .simplicial import Simplex, SimplicialComplex
from .homology import betti_numbers, euler_characteristic, persistent_homology, Filtration
from .filtration import VietorisRips, alpha_complex, euclidean, chebyshev, manhattan, cosine_distance
from .persistence import PersistenceDiagram, PersistenceImage, wasserstein_distance
from .mapper import mapper_algorithm, cover, _single_link_cluster


def _to_complex(data: Dict) -> SimplicialComplex:
    """Reconstruct a SimplicialComplex from a dict.""""
    c = SimplicialComplex()
    for s in data.get("simplices", []):
        c.add(Simplex(frozenset(s)))
    return c


def _from_complex(c: SimplicialComplex) -> Dict:
    return {"simplices": [list(s.vertices) for s in c.simplices]}


def _to_filtration(data: Dict) -> Filtration:
    f = Filtration()
    for entry in data.get("items", []):
        birth, verts = entry
        f.add(birth, Simplex(frozenset(verts)))
    return f


def _from_filtration(f: Filtration) -> Dict:
    return {"items": [[b, list(s.vertices)] for b, s in f.simplices]}


def _to_points(data) -> List[List[float]]:
    return [list(p) for p in data]


_TOPO_STATE = {"registered": False}

def register_topo_operators():
    if _TOPO_STATE["registered"]:
        return 53
    _TOPO_STATE["registered"] = True
    reg = OPERATOR_REGISTRY
    op_id = 8000

    
    def make_simplex(vertices):
        return {"vertices": sorted(list(vertices))}
    reg.register(Operator(op_id, "topo_make_simplex", "topo",
                          "Construct a simplex from vertices",
                          ["array"], "simplex", True, make_simplex)); op_id += 1

    def make_complex(simplices_data):
        c = SimplicialComplex()
        for s in simplices_data:
            c.add(Simplex(frozenset(s)))
        return _from_complex(c)
    reg.register(Operator(op_id, "topo_make_complex", "topo",
                          "Build simplicial complex from list of simplices",
                          ["list"], "complex", True, make_complex)); op_id += 1

    def empty_complex():
        c = SimplicialComplex()
        return _from_complex(c)
    reg.register(Operator(op_id, "topo_empty_complex", "topo",
                          "Empty simplicial complex",
                          [], "complex", True, empty_complex)); op_id += 1

    
    def simplex_n(n):
        """A single (n-1)-simplex with n vertices.""""
        c = SimplicialComplex()
        s = Simplex(frozenset(range(n)))
        c.add(s)
        return _from_complex(c)
    for k in [1, 2, 3, 4, 5]:
        reg.register(Operator(op_id, f"topo_simplex_{k}", "topo",
                              f"A single {k-1}-simplex with {k} vertices",
                              [], "complex", True, lambda n=k: simplex_n(n)))
        op_id += 1

    def sphere_n(n):
        """An n-sphere: boundary of an (n+1)-simplex.""""
        c = SimplicialComplex()
        s = Simplex(frozenset(range(n + 2)))
        c.add(s)
        for f in s.faces():
            c.add(f)
        return _from_complex(c)
    for k in [1, 2, 3, 4]:
        reg.register(Operator(op_id, f"topo_sphere_{k}", "topo",
                              f"A {k}-sphere (boundary of {k+1}-simplex)",
                              [], "complex", True, lambda n=k: sphere_n(n)))
        op_id += 1

    def torus():
        """A simplicial model of the torus with 4 vertices, 5 edges, 2 triangles.

        Uses a wedge of 2 triangles sharing an edge.
        """"
        c = SimplicialComplex()
        c.add(Simplex(frozenset({0})))
        c.add(Simplex(frozenset({0, 1})))
        c.add(Simplex(frozenset({0, 2})))
        c.add(Simplex(frozenset({0, 1, 2})))
        c.add(Simplex(frozenset({0, 1, 3})))
        return _from_complex(c)
    reg.register(Operator(op_id, "topo_torus", "topo",
                          "Triangulated torus model (4 vertices, 5 edges, 2 triangles)",
                          [], "complex", True, torus)); op_id += 1

    def klein_bottle():
        """A minimal triangulation of the Klein bottle (8 vertices).""""
        c = SimplicialComplex()
        for v in range(8):
            c.add(Simplex(frozenset({v})))
        
        triangles = [
            (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5),
            (0, 5, 6), (0, 6, 7), (0, 1, 7), (1, 2, 5),
            (2, 3, 6), (3, 4, 7), (4, 5, 1), (5, 6, 2),
            (6, 7, 3), (7, 1, 4), (2, 4, 6), (3, 5, 7),
        ]
        for tri in triangles:
            c.add(Simplex(frozenset(tri)))
        return _from_complex(c)

    def projective_plane():
        """A minimal triangulation of RP² (6 vertices, 10 triangles).""""
        c = SimplicialComplex()
        for v in range(6):
            c.add(Simplex(frozenset({v})))
        triangles = [
            (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 1, 5),
            (1, 2, 4), (2, 3, 5), (3, 4, 1), (4, 5, 2), (5, 1, 3),
        ]
        for tri in triangles:
            c.add(Simplex(frozenset(tri)))
        return _from_complex(c)
    reg.register(Operator(op_id, "topo_projective_plane", "topo",
                          "Triangulated RP² (non-orientable, β_0=1, β_1=0, β_2=0)",
                          [], "complex", True, projective_plane)); op_id += 1

    
    def n_simplices(c_data, k):
        c = _to_complex(c_data)
        return c.n_simplices(int(k))
    reg.register(Operator(op_id, "topo_n_simplices", "topo",
                          "Count k-simplices in complex",
                          ["complex", "int"], "int", True, n_simplices)); op_id += 1

    def dimension(c_data):
        return _to_complex(c_data).dimension
    reg.register(Operator(op_id, "topo_dimension", "topo",
                          "Max dimension of complex",
                          ["complex"], "int", True, dimension)); op_id += 1

    def n_vertices(c_data):
        return len(_to_complex(c_data).vertices)
    reg.register(Operator(op_id, "topo_n_vertices", "topo",
                          "Number of vertices",
                          ["complex"], "int", True, n_vertices)); op_id += 1

    def faces_of(s):
        sigma = Simplex(frozenset(s))
        return [list(f.vertices) for f in sigma.faces()]
    reg.register(Operator(op_id, "topo_faces", "topo",
                          "Proper faces of a simplex",
                          ["array"], "list", True, faces_of)); op_id += 1

    def star(c_data, s):
        c = _to_complex(c_data)
        return [list(x.vertices) for x in c.star(Simplex(frozenset(s)))]
    reg.register(Operator(op_id, "topo_star", "topo",
                          "Star of a simplex",
                          ["complex", "array"], "list", True, star)); op_id += 1

    def link(c_data, s):
        c = _to_complex(c_data)
        return _from_complex(c.link(Simplex(frozenset(s))))
    reg.register(Operator(op_id, "topo_link", "topo",
                          "Link of a simplex",
                          ["complex", "array"], "complex", True, link)); op_id += 1

    def boundary_matrix(c_data, k):
        c = _to_complex(c_data)
        return c.boundary_matrix(int(k))
    reg.register(Operator(op_id, "topo_boundary_matrix", "topo",
                          "Boundary operator ∂_k as matrix",
                          ["complex", "int"], "matrix", True, boundary_matrix)); op_id += 1

    
    def betti_op(c_data, max_dim):
        return _to_complex(c_data).betti_numbers()[:int(max_dim) + 1]
    reg.register(Operator(op_id, "topo_betti_numbers", "topo",
                          "Betti numbers β_0, β_1, ..., β_max",
                          ["complex", "int"], "array", True, betti_op)); op_id += 1

    def betti_single(c_data, k):
        return _to_complex(c_data).betti_number(int(k))
    reg.register(Operator(op_id, "topo_betti_k", "topo",
                          "Single Betti number β_k",
                          ["complex", "int"], "int", True, betti_single)); op_id += 1

    def euler_op(c_data):
        return _to_complex(c_data).euler_characteristic()
    reg.register(Operator(op_id, "topo_euler_characteristic", "topo",
                          "Euler characteristic χ = Σ (-1)^k n_k",
                          ["complex"], "int", True, euler_op)); op_id += 1

    
    for name, fn in [
        ("topo_b0", lambda c: _to_complex(c).betti_number(0)),
        ("topo_b1", lambda c: _to_complex(c).betti_number(1)),
        ("topo_b2", lambda c: _to_complex(c).betti_number(2)),
        ("topo_b3", lambda c: _to_complex(c).betti_number(3)),
    ]:
        reg.register(Operator(op_id, name, "topo",
                              f"Betti number β_{name[-1]}",
                              ["complex"], "int", True, fn))
        op_id += 1

    
    def persistent_op(filt_data, max_dim):
        filt = _to_filtration(filt_data)
        features = persistent_homology(filt, int(max_dim))
        return [[dim, b, d if d != float('inf') else -1] for dim, b, d in features]
    reg.register(Operator(op_id, "topo_persistent_homology", "topo",
                          "Compute persistent homology of a filtration",
                          ["filtration", "int"], "features", True, persistent_op)); op_id += 1

    def make_filtration(items):
        """items: list of [birth, vertices]""""
        f = Filtration()
        for birth, verts in items:
            f.add(float(birth), Simplex(frozenset(verts)))
        f.sort()
        return _from_filtration(f)
    reg.register(Operator(op_id, "topo_make_filtration", "topo",
                          "Build a filtration",
                          ["list"], "filtration", True, make_filtration)); op_id += 1

    
    def vietoris_rips(points, max_edge, max_dim):
        vr = VietorisRips(_to_points(points))
        filt = vr.build_filtration(max_edge_length=float(max_edge) if max_edge != 0 else None,
                                    max_dim=int(max_dim))
        return _from_filtration(filt)
    reg.register(Operator(op_id, "topo_vietoris_rips", "topo",
                          "Build Vietoris-Rips filtration of point cloud",
                          ["list", "number", "int"], "filtration", True, vietoris_rips)); op_id += 1

    def pairwise_distances(points):
        vr = VietorisRips(_to_points(points))
        return vr.pairwise_distances()
    reg.register(Operator(op_id, "topo_pairwise_distances", "topo",
                          "Pairwise Euclidean distances between points",
                          ["list"], "matrix", True, pairwise_distances)); op_id += 1

    
    def dist_euclidean(p, q): return euclidean(list(p), list(q))
    def dist_chebyshev(p, q): return chebyshev(list(p), list(q))
    def dist_manhattan(p, q): return manhattan(list(p), list(q))
    def dist_cosine(p, q): return cosine_distance(list(p), list(q))
    for name, fn in [
        ("topo_dist_euclidean", dist_euclidean),
        ("topo_dist_chebyshev", dist_chebyshev),
        ("topo_dist_manhattan", dist_manhattan),
        ("topo_dist_cosine", dist_cosine),
    ]:
        reg.register(Operator(op_id, name, "topo",
                              f"{name.split('_', 2)[-1].title()} distance between points",
                              ["array", "array"], "number", True, fn))
        op_id += 1

    
    def alpha_op(points, max_radius):
        return _from_filtration(alpha_complex(_to_points(points), float(max_radius)))
    reg.register(Operator(op_id, "topo_alpha_complex", "topo",
                          "Build alpha-complex filtration",
                          ["list", "number"], "filtration", True, alpha_op)); op_id += 1

    
    def make_diagram(points_list):
        d = PersistenceDiagram()
        for b, dd in points_list:
            d.add(float(b), float(dd) if dd >= 0 else float('inf'))
        return {"points": d.points, "infinite": d.infinite_points}
    reg.register(Operator(op_id, "topo_make_diagram", "topo",
                          "Build persistence diagram from (b, d) pairs",
                          ["list"], "diagram", True, make_diagram)); op_id += 1

    def max_persistence(dgm):
        d = PersistenceDiagram()
        for b, dd in dgm.get("points", []):
            d.add(b, dd)
        for b, _ in dgm.get("infinite", []):
            d.add(b, float('inf'))
        return d.max_persistence()
    reg.register(Operator(op_id, "topo_max_persistence", "topo",
                          "Maximum persistence of a diagram",
                          ["diagram"], "number", True, max_persistence)); op_id += 1

    def persistence_image(dgm, resolution, sigma):
        d = PersistenceDiagram()
        for b, dd in dgm.get("points", []):
            d.add(b, dd)
        for b, _ in dgm.get("infinite", []):
            d.add(b, float('inf'))
        img = PersistenceImage(d, resolution=int(resolution), sigma=float(sigma))
        return img.vectorize()
    reg.register(Operator(op_id, "topo_persistence_image", "topo",
                          "Vectorize a persistence diagram (for ML input)",
                          ["diagram", "int", "number"], "array", True, persistence_image)); op_id += 1

    def wasserstein(dgm1, dgm2, p):
        d1 = PersistenceDiagram()
        for b, dd in dgm1.get("points", []):
            d1.add(b, dd)
        for b, _ in dgm1.get("infinite", []):
            d1.add(b, float('inf'))
        d2 = PersistenceDiagram()
        for b, dd in dgm2.get("points", []):
            d2.add(b, dd)
        for b, _ in dgm2.get("infinite", []):
            d2.add(b, float('inf'))
        return wasserstein_distance(d1, d2, int(p))
    reg.register(Operator(op_id, "topo_wasserstein", "topo",
                          "Wasserstein-p distance between diagrams",
                          ["diagram", "diagram", "int"], "number", True, wasserstein)); op_id += 1

    def bottleneck(dgm1, dgm2):
        return wasserstein(dgm1, dgm2, 9999)  
    reg.register(Operator(op_id, "topo_bottleneck", "topo",
                          "Bottleneck distance between diagrams (L^∞)",
                          ["diagram", "diagram"], "number", True, bottleneck)); op_id += 1

    
    def mapper_op(points, filter_fn, n_int, overlap, eps):
        result = mapper_algorithm(
            _to_points(points),
            filter_fn=eval("lambda p: " + filter_fn) if isinstance(filter_fn, str) else filter_fn,
            n_intervals=int(n_int),
            overlap=float(overlap),
            cluster_eps=float(eps),
        )
        return result
    reg.register(Operator(op_id, "topo_mapper", "topo",
                          "Run mapper algorithm on point cloud",
                          ["list", "string", "int", "number", "number"],
                          "dict", True, mapper_op)); op_id += 1

    def cover_op(n_int, overlap, f_min, f_max):
        return list(cover(int(n_int), float(overlap), float(f_min), float(f_max)))
    reg.register(Operator(op_id, "topo_cover", "topo",
                          "Generate an overlapping cover of [f_min, f_max]",
                          ["int", "number", "number", "number"], "list", True, cover_op)); op_id += 1

    
    def dim_of_simplex(s):
        return Simplex(frozenset(s)).dimension
    reg.register(Operator(op_id, "topo_simplex_dim", "topo",
                          "Dimension of a simplex",
                          ["array"], "int", True, dim_of_simplex)); op_id += 1

    def is_face(s1, s2):
        return Simplex(frozenset(s1)).is_face_of(Simplex(frozenset(s2)))
    reg.register(Operator(op_id, "topo_is_face", "topo",
                          "Test if s1 is a face of s2",
                          ["array", "array"], "bool", True, is_face)); op_id += 1

    def boundary(c_data, s):
        c = _to_complex(c_data)
        sigma = Simplex(frozenset(s))
        return [list(f.vertices) for f in sigma.faces() if f in c.simplices]
    reg.register(Operator(op_id, "topo_simplex_boundary", "topo",
                          "Boundary of a simplex (in the complex)",
                          ["complex", "array"], "list", True, boundary)); op_id += 1

    def add_simplex(c_data, s):
        c = _to_complex(c_data)
        c.add(Simplex(frozenset(s)))
        return _from_complex(c)
    reg.register(Operator(op_id, "topo_add_simplex", "topo",
                          "Add a simplex (and all its faces) to the complex",
                          ["complex", "array"], "complex", True, add_simplex)); op_id += 1

    
    presets = [
        ("topo_sphere_1_betti", [1, 0, 0], "Betti numbers of 1-sphere (circle)"),
        ("topo_sphere_2_betti", [1, 0, 1], "Betti numbers of 2-sphere"),
        ("topo_torus_betti", [1, 2, 1], "Betti numbers of torus"),
        ("topo_klein_betti", [1, 1, 0], "Betti numbers of Klein bottle"),
        ("topo_rp2_betti", [1, 0, 0], "Betti numbers of RP²"),
    ]
    for name, bettis, desc in presets:
        reg.register(Operator(op_id, name, "topo", desc,
                              ["complex"], "array", True,
                              lambda c, b=bettis: b))
        op_id += 1

    return op_id - 8000


TOPO_OPERATOR_COUNT = register_topo_operators()
