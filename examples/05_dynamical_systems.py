"""
05 — Dynamical Systems: chaos, fractals, Lyapunov exponents.

Quantify the predictability horizon of any iterative process. The
Lyapunov exponent is positive for chaos, negative for stable attractors.
"""
import random
from minxg.chaos import (
    logistic_map, logistic_lyapunov, lorenz,
    sierpinski_gasket, koch_snowflake, dragon_curve,
    kaplan_yorke_dimension, feigenbaum_constant,
)
random.seed(42)

stable = logistic_lyapunov(r=3.2)
chaotic = logistic_lyapunov(r=3.9)
print(f"Lyapunov at r=3.2 (stable):   {stable:+.4f}  (negative)")
print(f"Lyapunov at r=3.9 (chaos):    {chaotic:+.4f}  (positive)")
assert stable < 0
assert chaotic > 0

traj = lorenz(10, 28, 8/3, 0.1, 0.1, 0.1, dt=0.01, n=2000)
xs = [p[0] for p in traj]
ys = [p[1] for p in traj]
zs = [p[2] for p in traj]
print(f"\nLorenz attractor (final state after 2000 steps):")
print(f"  x: {xs[-1]:.2f}  y: {ys[-1]:.2f}  z: {zs[-1]:.2f}")
print(f"  (butterfly-like range, stays bounded)")

sierp = sierpinski_gasket(n_points=5000)
koch = koch_snowflake(n_points=2000)
dragon = dragon_curve(n_points=2000)
print(f"\nfractals generated:")
print(f"  Sierpinski gasket: {len(sierp)} points  (D ≈ 1.585)")
print(f"  Koch snowflake:    {len(koch)} points   (D ≈ 1.262)")
print(f"  Heighway dragon:   {len(dragon)} points")
assert all(0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p in sierp[:100])

lyap_spectrum = [0.9, 0.0, -14.5]
d_ky = kaplan_yorke_dimension(lyap_spectrum)
print(f"\nKaplan-Yorke dimension of Lorenz attractor: {d_ky:.3f}")
print(f"  (analytical ≈ 2.06)")

delta = feigenbaum_constant()
print(f"\nFeigenbaum constant δ = {delta:.10f}")
print(f"  (universal ratio of period-doubling bifurcations)")
assert abs(delta - 4.6692016) < 0.001

print("\nall assertions passed")
