"""
01 — Geometric Algebra: rotate, reflect, dilate.

The unified type for rigid motions and scalings. One algebraic
framework works in any dimension and any signature.
""""
import math
from minxg.ga import Multivector, Signature, Rotor, Reflector, Dilator

sig = Signature(3, 0)
e1 = Multivector({1: 1.0}, sig)
e2 = Multivector({2: 1.0}, sig)
e3 = Multivector({4: 1.0}, sig)

B_xy = e1.outer(e2).normalize()
R = Rotor.from_bivector(B_xy, math.pi / 2)
v_rotated = R.apply(e1)
print(f"rotate e1 by 90° in xy-plane: {v_rotated}")
assert abs(v_rotated[2] - 1.0) < 1e-9, f"expected e2, got {v_rotated}"

n = Multivector({1: 1.0, 2: 0.0, 4: 0.0}, sig)
ref = Reflector.from_normal(n)
v_reflected = ref.apply(e2)
print(f"reflect e2 through x-axis: {v_reflected}")
assert abs(v_reflected[2] + 1.0) < 1e-9

D = Dilator.from_scale(2.0, sig)
v_scaled = D.apply(e1)
print(f"scale e1 by 2: {v_scaled}")
assert abs(v_scaled[1] - 2.0) < 1e-9

v1 = Multivector({1: 1.0, 2: 2.0, 4: 3.0}, sig)
v2 = Multivector({2: 1.0, 4: 1.0}, sig)
prod = v1 * v2
print(f"(e1 + 2 e2 + 3 e3) * (e2 + e3) = {prod}")
sq = v1 * v1
print(f"v1² = {sq[0]}  (Euclidean: should be 1+4+9=14)")
assert abs(sq[0] - 14.0) < 1e-9

print("\nall assertions passed")
