# Information Geometry

> Pillar 3 of 6 in MINXG. 51 operators in IDs 7000-7050.

Probability distributions form a **Riemannian manifold** with the Fisher
information matrix as the metric. Amari's α-connection generalizes the
exponential and mixture connections. The **natural gradient** is
reparameterization-invariant.

## Quick example

```python
from minxg.infogeo import Gaussian, fisher_information_matrix, natural_gradient
g = Gaussian()
F = fisher_information_matrix(g, [0.0, 1.0], n_samples=1000)
nat_grad = natural_gradient([0.5, 0.1], F)
```

## What's in here

| File | Purpose |
|------|---------|
| `manifold.py` | `StatisticalManifold`, `DistributionFamily`, ExponentialFamily, MixtureFamily |
| `fisher.py` | Fisher information, natural gradient, KFAC |
| `connection.py` | α-connection, parallel transport, exponential map |
| `divergence.py` | KL, JS, Rényi, Bregman, Hellinger, TV divergences |
| `operators_ig.py` | Operator registration (pure Python, no numpy) |

## Why this matters for AI

1. Reparameterization invariance
2. Faster convergence in variational inference and training
3. Proper loss functions for generative models
4. Geometric understanding of EM algorithm

## References

- Amari, "Information Geometry and Its Applications" (2016)
- Ay et al., "Information Geometry" (2017)

See also: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)
