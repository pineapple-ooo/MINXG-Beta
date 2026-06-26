# Algebraic Topology

> Pillar 4 of 6 in MINXG. 53 operators in IDs 8000-8052.

**Topological Data Analysis** primitives as first-class operators.
Persistent homology (H₀, H₁, H₂), Betti numbers, persistence diagrams,
Wasserstein distance, Mapper algorithm — all in pure Python.

## Quick example

```python
from minxg.topo import Simplex, SimplicialComplex, VietorisRips
import random
random.seed(42)

c = SimplicialComplex()
c.add(Simplex(frozenset({0, 1, 2, 3})))
print(c.betti_numbers(), c.euler_characteristic())

points = [[random.gauss(0, 1), random.gauss(0, 1)] for _ in range(20)]
vr = VietorisRips(points)
filt = vr.build_filtration(max_edge_length=2.0, max_dim=2)
print(f"VR filtration: {len(filt.simplices)} simplices")
```

## What's in here

| File | Purpose |
|------|---------|
| `simplicial.py` | `Simplex`, `SimplicialComplex`, Betti numbers, Euler |
| `homology.py` | Persistent homology, filtration |
| `filtration.py` | Vietoris-Rips, alpha complex, distance functions |
| `persistence.py` | Persistence diagrams, images, Wasserstein |
| `mapper.py` | Mapper algorithm, covers |
| `operators_topo.py` | Operator registration |

## Why this matters for AI

1. Loss landscapes have topological structure
2. Embedding manifolds have non-trivial topology
3. Persistent features are scale-invariant
4. Wasserstein distance is a proper metric on topological features

## Known limitations

- **Betti numbers on dense / periodic complexes** (e.g. sampling a
  torus on a regular grid) may disagree with the theoretical value by
  ±1 on `b₁` / `b₂`. The cause is numerical round-off in column
  reduction of boundary matrices over floating-point coefficients
  (Smith Normal Form over ℤ is robust; over ℝ it is not).
  - **Workaround**: pass `integer_snf=True` if your complexes are
    built from integer coordinates — at the cost of ~10× slower.
  - **Status**: tracked, not blocking the rest of the pillar.
  - **Architectural call**: registration, dispatch, and category
    logic are unaffected — only the homology-class output diverges in
    edge cases. PRs welcome; see `homology.py:_betti_via_smith()`.

## References

- Edelsbrunner & Harer, "Computational Topology" (2010)
- Carlsson, "Topology and Data" (2009)
- Adams et al., "Persistence Images" (2017)

See also: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)
