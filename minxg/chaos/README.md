# Dynamical Systems & Chaos

> Pillar 5 of 6 in MINXG. 23 operators in IDs 8500-8522.

Discrete maps (logistic, Henon), continuous systems (Lorenz, Rössler,
Duffing), Lyapunov exponents, fractal dimensions, IFS, bifurcation
diagrams. All in pure Python.

## Quick example

```python
from minxg.chaos import logistic_lyapunov, logistic_map, lorenz

lyap = logistic_lyapunov(r=3.9)
print(f"Lyapunov: {lyap:.4f}  (>0 = chaos)")

seq = logistic_map(r=3.9, x0=0.5, n=30)
traj = lorenz(10, 28, 8/3, 0.1, 0.1, 0.1, 0.01, 1000)
```

## What's in here

| File | Purpose |
|------|---------|
| `maps.py` | Logistic, Henon, Lorenz, Rössler, Duffing |
| `lyapunov.py` | Lyapunov exponents (1D and spectrum) |
| `fractal.py` | Box-counting, Hausdorff, correlation, Kaplan-Yorke |
| `bifurcation.py` | Bifurcation diagrams |
| `ifs.py` | Sierpinski, Koch, Barnsley fern, dragon curve |
| `operators_chaos.py` | Operator registration |

## Why this matters for AI

1. Quantify the predictability horizon of any iterative process
2. Detect when training enters chaotic regimes
3. Analyze the topology of generated distributions
4. Generate fractal structures

## References

- Strogatz, "Nonlinear Dynamics and Chaos" (2015)
- Peitgen et al., "Chaos and Fractals" (2004)
- Feigenbaum, "Quantitative Universality" (1978)

See also: [ARCHITECTURE.md](../../ARCHITECTURE.md) · [PROJECT_INDEX.md](../../PROJECT_INDEX.md)
