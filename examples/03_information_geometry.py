"""
03 — Information Geometry: Fisher metric, natural gradient, divergences.

The space of probability distributions is a Riemannian manifold. The
natural gradient is the correct optimization step on that manifold.
"""
from minxg.infogeo import (
    Gaussian, Bernoulli,
    fisher_information_matrix, natural_gradient,
    parametric_kl, js_divergence, hellinger_distance,
)

g = Gaussian()
theta = [0.0, 1.0]
F = fisher_information_matrix(g, theta, n_samples=2000)
print(f"Fisher information matrix of N(0,1):")
print(f"  [{F[0][0]:.3f}  {F[0][1]:.3f}]")
print(f"  [{F[1][0]:.3f}  {F[1][1]:.3f}]")
print(f"  (analytical: [[1, 0], [0, 2]])")
assert abs(F[0][0] - 1.0) < 0.1
assert abs(F[1][1] - 2.0) < 0.2

std_grad = [0.5, 0.1]
nat_grad = natural_gradient(std_grad, F, regularization=1e-6)
print(f"\nstandard gradient: {std_grad}")
print(f"natural gradient:   {[round(g, 4) for g in nat_grad]}")
assert nat_grad != std_grad

g1 = Gaussian()
g2 = Gaussian()
kl = parametric_kl(g1, g2, [0.0, 1.0], [1.0, 1.0], n_samples=2000)
js = js_divergence(g1, g2, [0.0, 1.0], [1.0, 1.0], n_samples=2000)
hel = hellinger_distance(g1, g2, [0.0, 1.0], [1.0, 1.0], n_samples=2000)
print(f"\nKL(N(0,1) || N(1,1))  ≈ {kl:.4f}  (exact: 0.5)")
print(f"JS(N(0,1), N(1,1))  ≈ {js:.4f}")
print(f"Hellinger(N(0,1), N(1,1))  ≈ {hel:.4f}")
assert 0.4 < kl < 0.6
assert 0.0 < js < 0.7
assert 0.0 < hel < 1.0

b = Bernoulli()
samples = b.sample([0.7], 5000)
empirical_mean = sum(samples) / len(samples)
print(f"\nBernoulli(0.7) sample mean: {empirical_mean:.3f}  (true: 0.7)")
assert abs(empirical_mean - 0.7) < 0.05

print("\nall assertions passed")
