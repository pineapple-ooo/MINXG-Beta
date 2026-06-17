# Fiber Bundles

> Pillar 6 of 6 in MINXG. 53 operators in IDs 6000-6052.

The unifying language of gauge theory, general relativity, and modern
condensed matter. Includes connections, parallel transport, curvature
(Riemann, Ricci, scalar), covariant derivatives, geodesics, and
vielbeins for spin structures.

## Quick example

```python
from minxg.fiber import (
    Connection, ParallelTransport, Curvature,
    TangentBundle, RiemannianMetric,
)
import math

conn = Connection(dim=2)
pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
v_transported = pt.transport([1.0, 0.0], n_steps=100)

curv = Curvature(conn)
R = curv.riemann_tensor([0.0, 0.0])

tb = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, 1]]))
geodesic = tb.geodesic([0, 0], [0, 1], t_max=1.0, n_steps=10)
```

## What's in here

| File | Purpose |
|------|---------|
| `bundle.py` | FiberBundle, VectorBundle, PrincipalBundle |
| `connection.py` | Connection, ParallelTransport, Curvature (Riemann, Ricci, scalar) |
| `section.py` | Section, CovariantDerivative |
| `tangent.py` | TangentBundle, RiemannianMetric, Levi-Civita, geodesics |
| `frame.py` | FrameBundle, Vielbein |
| `operators_fiber.py` | Operator registration |

## Why this matters for AI

1. Embedding spaces are often bundles (sphere = SO(3)/SO(2))
2. Gauge invariance underlies attention mechanisms
3. Parallel transport defines natural way to compare vectors
4. Curvature quantifies "how non-Euclidean" the space is

## References

- Nakahara, "Geometry, Topology and Physics" (2003)
- Frankel, "The Geometry of Physics" (2011)
- Baez & Muniain, "Gauge Fields, Knots and Gravity" (1994)

See also: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)
