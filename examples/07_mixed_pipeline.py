"""
07 — Mixed pipeline: chain all six pillars in one program.

Demonstrates how the pillars compose. A typical ML/AI workflow
might use:
  - GA to rotate embeddings
  - CAT to chain operator types
  - IG to compute the natural gradient
  - TOPO to detect regime changes via persistent homology
  - CHAOS to monitor Lyapunov and avoid chaotic training
  - FIBER for the underlying manifold structure
"""
import math
import minxg.cat as cat
from minxg.ga import Multivector, Signature, Rotor
from minxg.infogeo import (
    fisher_information_matrix, natural_gradient, Gaussian,
)
from minxg.chaos import logistic_lyapunov
from minxg.topo import Simplex, SimplicialComplex
from minxg.fiber import TangentBundle, RiemannianMetric
from minxg.operators import OPERATOR_REGISTRY

print("=" * 60)
print("MINXG: mixing all six mathematical pillars in one workflow")
print("=" * 60)

print(f"\n[registry] {OPERATOR_REGISTRY.total_operators} operators in {len(OPERATOR_REGISTRY.list_categories())} categories")
ga_ops = OPERATOR_REGISTRY.get_category("ga")
print(f"[ga]      {len(ga_ops)} operators, e.g. {ga_ops[0].name}, {ga_ops[1].name}")

sig = Signature(3, 0)
e1 = Multivector({1: 1.0}, sig)
e2 = Multivector({2: 1.0}, sig)
B = e1.outer(e2).normalize()
R = Rotor.from_bivector(B, math.pi / 4)
print(f"[ga]      rotated e1 by 45°: {R.apply(e1)}")

normalize = cat.Morphism("normalize", (cat.Type("number"),), cat.Type("number"), lambda x: max(0, min(1, x)))
scale = cat.Morphism("scale", (cat.Type("number"),), cat.Type("number"), lambda x: x * 100)
pipeline = normalize >> scale
print(f"[cat]     pipeline(normalize → scale): {pipeline(0.5)}")

g = Gaussian()
F = fisher_information_matrix(g, [0.0, 1.0], n_samples=500)
nat_grad = natural_gradient([0.1, 0.05], F, regularization=1e-4)
print(f"[ig]      natural gradient for N(0,1): {[round(x, 3) for x in nat_grad]}")

c = SimplicialComplex()
for i, j in [(0, 1), (1, 2), (2, 0)]:
    c.add(Simplex(frozenset({i, j})))
c.add(Simplex(frozenset({0, 1, 2})))
print(f"[topo]    triangle Betti: {c.betti_numbers()}, Euler: {c.euler_characteristic()}")

lyap = logistic_lyapunov(3.5)
status = "chaotic" if lyap > 0 else "stable"
print(f"[chaos]   Lyapunov at r=3.5: {lyap:+.4f}  ({status})")

tb = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, 1]]))
geo = tb.geodesic([0, 0], [3, 4], t_max=1.0, n_steps=10)
print(f"[fiber]   Euclidean geodesic end: {geo[-1]}")

print("\n" + "=" * 60)
print("all six pillars working together")
print("=" * 60)
