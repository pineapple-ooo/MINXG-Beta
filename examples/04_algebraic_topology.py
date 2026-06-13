"""
04 — Algebraic Topology: simplicial complexes, Betti numbers, persistence.

The shape of data: connected components, loops, voids. Persistent
homology tracks how these features appear and disappear across scales.
""""
import random
from minxg.topo import (
    Simplex, SimplicialComplex,
    VietorisRips, Filtration,
    persistent_homology,
    PersistenceDiagram, PersistenceImage, wasserstein_distance,
)
random.seed(42)

c = SimplicialComplex()
c.add(Simplex(frozenset({0, 1, 2})))
betti = c.betti_numbers()
euler = c.euler_characteristic()
print(f"single triangle:")
print(f"  Betti:  {betti}  (β₀=1 connected, β₁=0 no loop)")
print(f"  Euler:  {euler}  (= 3 - 3 + 1 = 1 for a triangle with 3 vertices)")
assert betti[:2] == [1, 0]
assert euler == 1

points = [[random.gauss(0, 1), random.gauss(0, 1)] for _ in range(30)]
vr = VietorisRips(points)
filt = vr.build_filtration(max_edge_length=2.0, max_dim=2)
features = persistent_homology(filt, max_dim=1)
print(f"\nVR filtration on 30 random points:")
print(f"  simplices: {len(filt.simplices)}")
print(f"  features:  {len(features)}")
assert len(filt.simplices) > 100

d1 = PersistenceDiagram()
d1.add(0.1, 0.5)
d1.add(0.2, 0.8)
d2 = PersistenceDiagram()
d2.add(0.15, 0.6)
d2.add(0.25, 0.9)
d = wasserstein_distance(d1, d2, p=2)
print(f"\nWasserstein-2 distance between two diagrams: {d:.4f}")
assert 0 < d < 0.5

img = PersistenceImage(d1, resolution=8, sigma=0.1)
features_vec = img.vectorize()
print(f"persistence image vector length: {len(features_vec)} (8x8=64)")
assert len(features_vec) == 64

print("\nall assertions passed")
