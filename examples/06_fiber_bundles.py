"""
06 — Fiber Bundles: connections, curvature, geodesics, parallel transport.

The unifying language of gauge theory. The curvature tensor tells you
how non-Euclidean your space is.
""""
import math
from minxg.fiber import (
    Connection, ParallelTransport, Curvature,
    TangentBundle, RiemannianMetric,
)

conn = Connection(dim=2)
pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
v_initial = [1.0, 0.0]
v_transported = pt.transport(v_initial, n_steps=200)
print(f"parallel transport of {v_initial} along parabola:")
print(f"  transported: {[round(x, 4) for x in v_transported]}")
print(f"  (along a curve in flat space → approximately preserved)")

curv = Curvature(conn)
R = curv.riemann_tensor([0.0, 0.0])
max_R = max(abs(R[i][j][k][l]) for i in range(2) for j in range(2) for k in range(2) for l in range(2))
print(f"\ncurvature tensor (max abs component): {max_R:.2e}")
print(f"  (zero connection → zero curvature, as expected)")
assert max_R < 1e-9

tb = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, 1]]))
geodesic = tb.geodesic([0, 0], [1, 0], t_max=2.0, n_steps=20)
print(f"\nEuclidean geodesic (straight line): start=[0,0], v=[1,0], t=2")
print(f"  endpoints: {geodesic[0]} → {geodesic[-1]}")
assert abs(geodesic[-1][0] - 2.0) < 0.01
assert abs(geodesic[-1][1] - 0.0) < 0.01

sphere = TangentBundle(2, RiemannianMetric(lambda p: [[1, 0], [0, math.sin(p[0])**2]]))
geo_sphere = sphere.geodesic([math.pi/2, 0], [0, 1], t_max=math.pi, n_steps=50)
print(f"\nsphere geodesic from (π/2, 0) along equator:")
print(f"  length around the equator: t_max = π (half-circumference)")
print(f"  endpoints: ({geo_sphere[-1][0]:.3f}, {geo_sphere[-1][1]:.3f})")
assert abs(geo_sphere[-1][0] - math.pi/2) < 0.01
assert abs(geo_sphere[-1][1] - math.pi) < 0.01

print("\nall assertions passed")
