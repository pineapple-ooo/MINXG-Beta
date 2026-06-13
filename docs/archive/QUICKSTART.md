# QUICKSTART

> 5-minute tour of all 6 mathematical pillars.
> For the full architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 1 · Geometric Algebra: rotate a vector in 3D

```python
from minxg.ga import Multivector, Signature, Rotor
import math

sig = Signature(3, 0)
e1 = Multivector({1: 1.0}, sig)
e3 = Multivector({4: 1.0}, sig)

B = e3.outer(e1).normalize()
R = Rotor.from_bivector(B, math.pi / 2)

e1_rotated = R.apply(e1)
print(f"R(e1) = {e1_rotated}")
```

The SAME `Rotor` class works in any dimension, any signature.

## 2 · Category Theory: type-safe composition

```python
from minxg.cat import Morphism, identity, compose

int_to_str = Morphism("int_to_str", ("int",), "string", str)
str_to_len = Morphism("str_to_len", ("string",), "int", len)

pipeline = int_to_str >> str_to_len
print(pipeline(42))

try:
    bad = str_to_len >> int_to_str
except TypeError as e:
    print(f"Type error caught: {e}")
```

Composition is type-checked at construction time.

## 3 · Information Geometry: natural gradient

```python
from minxg.infogeo import Gaussian, fisher_information_matrix, natural_gradient

g = Gaussian()
theta = [0.0, 1.0]
F = fisher_information_matrix(g, theta, n_samples=1000)
print(f"Fisher matrix:\n  [{F[0][0]:.3f}, {F[0][1]:.3f}]\n  [{F[1][0]:.3f}, {F[1][1]:.3f}]")

std_grad = [0.5, 0.1]
nat_grad = natural_gradient(std_grad, F, regularization=1e-6)
print(f"Natural gradient: {[round(g, 4) for g in nat_grad]}")
```

## 4 · Algebraic Topology: persistent homology

```python
from minxg.topo import VietorisRips, Simplex, SimplicialComplex
import random
random.seed(42)

points = [[random.gauss(0, 1), random.gauss(0, 1)] for _ in range(20)]

vr = VietorisRips(points)
filtration = vr.build_filtration(max_edge_length=2.0, max_dim=2)
print(f"Filtration: {len(filtration.simplices)} simplices")

c = SimplicialComplex()
c.add(Simplex(frozenset({0, 1, 2, 3})))
print(f"Tetrahedron Betti: {c.betti_numbers()}")
print(f"Tetrahedron Euler: {c.euler_characteristic()}")
```

## 5 · Dynamical Systems: Lyapunov exponent

```python
from minxg.chaos import logistic_map, logistic_lyapunov, lorenz

seq = logistic_map(r=3.9, x0=0.5, n=30)
print(f"Logistic r=3.9 last 5: {[round(x, 3) for x in seq[-5:]]}")

lyap = logistic_lyapunov(r=3.9)
print(f"Lyapunov at r=3.9: {lyap:.4f}  (>0 = chaos)")

traj = lorenz(10, 28, 8/3, 0.1, 0.1, 0.1, 0.01, 1000)
print(f"Lorenz final: ({traj[-1][0]:.2f}, {traj[-1][1]:.2f}, {traj[-1][2]:.2f})")
```

## 6 · Fiber Bundles: parallel transport + curvature

```python
from minxg.fiber import Connection, ParallelTransport, Curvature, TangentBundle, RiemannianMetric

conn = Connection(dim=2)
pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
v_transported = pt.transport([1.0, 0.0], n_steps=100)
print(f"Parallel transport: {v_transported}")

curv = Curvature(conn)
R = curv.riemann_tensor([0.0, 0.0])
print(f"Riemann tensor shape: {len(R)} x {len(R[0])} x {len(R[0][0])} x {len(R[0][0][0])}")

tb = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, 1]]))
geodesic = tb.geodesic([0, 0], [0, 1], t_max=1.0, n_steps=10)
print(f"Euclidean geodesic: {geodesic[-1]}")
```

## All six pillars at once

```python
import minxg
print(f"MINXG: {minxg.get('project.name')} v{minxg.get('project.version')}")
print(f"  Pillars: {len(minxg.get('pillars', []))}")
print(f"  Operators: {minxg.get('operators.total')}")
```

## Where to go next

- [ARCHITECTURE.md](ARCHITECTURE.md) — full architecture
- [OPERATORS.md](OPERATORS.md) — all 376 operators
- [EXTENSIONS.md](EXTENSIONS.md) — build your own
- [SELF_EVOLUTION.md](SELF_EVOLUTION.md) — the 10 algorithms
