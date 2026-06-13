# MINXG — Multi-Language AI Orchestration Framework

> **Six mathematical pillars. 376 operators. 100% pure Python.震碎其他 AI Agent 世界观.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Operators: 376](https://img.shields.io/badge/operators-376-green.svg)](OPERATORS.md)
[![Pillars: 6](https://img.shields.io/badge/pillars-6-orange.svg)](ARCHITECTURE.md)
[![Tests](https://img.shields.io/badge/tests-66%20passed-brightgreen.svg)](tests/)
[![CI](https://img.shields.io/github/actions/workflow/status/minxg-source/minxg/ci.yml?branch=main&label=CI)](https://github.com/minxg-source/minxg/actions/workflows/ci.yml)

[English](README.md) | [简体中文](README.zh.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

---

## What is MINXG?

MINXG is a pure-Python AI orchestration framework whose **operator set is
grounded in six mathematical pillars** that no other AI framework exposes
as first-class primitives.

Where other frameworks treat operators as Python callables, MINXG
treats them as:

1. **Multivectors** in a Clifford Algebra — unified rotations, reflections, dilations
2. **Morphisms** in a Category — type-checked, composable, with functor/monad structure
3. **Points** on a Statistical Manifold — natural gradient, Fisher metric, α-connections
4. **Features** in a Topological Space — persistent homology, Betti numbers, manifold shapes
5. **Trajectories** in a Dynamical System — Lyapunov exponents, attractors, fractals
6. **Sections** of a Fiber Bundle — connections, parallel transport, curvature

**376 operators · 11 categories · 6 mathematical pillars · 100% pure Python.**

---

## 30-second quickstart

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e .
```

```python
import minxg
from minxg.operators import OPERATOR_REGISTRY

print(f"{OPERATOR_REGISTRY.total_operators} operators in {len(OPERATOR_REGISTRY.list_categories())} categories")
```

---

## Six pillars, one example each

### Geometric Algebra — rotate a vector in 3D

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

### Category Theory — type-safe composition

```python
from minxg.cat import Morphism

f = Morphism("f", ("int",), "string", str)
g = Morphism("g", ("string",), "int", len)
pipeline = f >> g
print(pipeline(42))
```

### Information Geometry — natural gradient

```python
from minxg.infogeo import Gaussian, fisher_information_matrix, natural_gradient
g = Gaussian()
F = fisher_information_matrix(g, [0.0, 1.0], n_samples=1000)
nat_grad = natural_gradient([0.5, 0.1], F)
```

### Algebraic Topology — Betti numbers

```python
from minxg.topo import Simplex, SimplicialComplex
c = SimplicialComplex()
c.add(Simplex(frozenset({0, 1, 2, 3})))
print(c.betti_numbers())
```

### Dynamical Systems — Lyapunov exponent

```python
from minxg.chaos import logistic_lyapunov
lyap = logistic_lyapunov(r=3.9)
print(f"Lyapunov exponent: {lyap:.4f}")
```

### Fiber Bundles — parallel transport + curvature

```python
from minxg.fiber import Connection, ParallelTransport, Curvature

conn = Connection(dim=2)
pt = ParallelTransport(conn, lambda t: [t, t**2], 0.0, 1.0)
v_transported = pt.transport([1.0, 0.0])

curv = Curvature(conn)
R = curv.riemann_tensor([0.0, 0.0])
```

---

## Why is MINXG different?

| Framework | Operator model | Type system | Composition |
|-----------|----------------|-------------|-------------|
| LangChain  | dict of name→callable | string tags | ad-hoc |
| AutoGen    | async function | Python types | manual |
| CrewAI     | class instance | duck typing | implicit |
| **MINXG**  | **morphism in category** | **type-theoretic** | **automatic, type-checked** |

The six mathematical pillars give you properties no other framework has:

1. **Mathematical guarantees** — operator composition is type-checked
2. **Parameterization invariance** — natural gradient is invariant under reparameterization
3. **Topological features** — persistent homology reveals structure no statistical method can detect
4. **Geometric operations** — rotors, reflections, dilations are single operations
5. **Chaos-aware computation** — Lyapunov exponents and bifurcation diagrams quantify predictability
6. **Gauge-theoretic structure** — fiber bundles, parallel transport, curvature

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              APPLICATION LAYER (agents, extensions)         │
├─────────────────────────────────────────────────────────────┤
│              SELF-EVOLUTION LAYER                           │
│   (behavioral isomorphism, ISG, NCD, 10 original algos)    │
├─────────────────────────────────────────────────────────────┤
│  GA 47 │ CAT 79 │ IG 51 │ TOPO 53 │ CHAOS 23 │ FIBER 53    │
│  (5000-5049)(4000-4078)(7000-7050)(8000-8052)(8500-8522)   │
│                              (6000-6052)                    │
├─────────────────────────────────────────────────────────────┤
│              PYTHON OPERATOR REGISTRY (376 ops)             │
│  math 20 │ text 19 │ data 12 │ logic 13 │ system 6         │
├─────────────────────────────────────────────────────────────┤
│              TIDAL LOCK C ACCELERATION                      │
├─────────────────────────────────────────────────────────────┤
│              WORKER LAYER (50+ workers)                     │
│  FS • Network • State • Crypto • ML • System • Process     │
└─────────────────────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.

---

## Self-Evolution Engine

MINXG learns from every interaction using **10 original algorithms** of
behavioral isomorphism (see [SELF_EVOLUTION.md](SELF_EVOLUTION.md)):

- **ISG** — Interaction Structure Graph (content-free)
- **NCD** — Normalized Compression Distance (language-agnostic)
- **SIG** — Spectral Invariant Signature (graph isomorphism invariant)
- **SIC** — Structural Isomorphism Class (hierarchical clustering)
- **BSP** — Behavioral Phase Space (32-dim trajectory)
- **BMO** — Behavioral Momentum (predictive)
- **TINV** — Topological Invariants (persistence homology)
- **SD** — Structural Drift (regime change detection)
- **INV** — Behavioral Invariants (stable features)
- **PVT** — Perturbation Validation (sandboxed)

These algorithms are STRUCTURALLY novel (geometric/topological), not
lexical (regex) or semantic (embeddings). They detect behavioral patterns
across languages and modalities.

---

## Performance

| Operation | Pure Python | Tidal Lock C | Speedup |
|-----------|-------------|--------------|---------|
| NCD (1KB text) | 850 μs | 12 μs | 70x |
| Phase embedding | 1.2 ms | 45 μs | 27x |
| zstd compression | 320 μs | 18 μs | 18x |
| xxhash3 | 0.5 μs | 0.02 μs | 25x |

---

## Installation

```bash
# Pure Python core
pip install -e .

# With C acceleration
cd c_core && make && cd ..
```

See [INSTALL.md](INSTALL.md) for full instructions including
Termux/Android.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [PROJECT_INDEX.md](PROJECT_INDEX.md) | One-page map of the whole project |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture in detail |
| [INSTALL.md](INSTALL.md) | Install everywhere (Linux, macOS, Termux) |
| [QUICKSTART.md](QUICKSTART.md) | 5-minute tour of all 6 pillars |
| [OPERATORS.md](OPERATORS.md) | All 376 operators with IDs and signatures |
| [EXTENSIONS.md](EXTENSIONS.md) | Build your own operators, workers, pillars |
| [SELF_EVOLUTION.md](SELF_EVOLUTION.md) | The 10 behavioral algorithms |
| [TIDAL_LOCK.md](TIDAL_LOCK.md) | C/C++/Go acceleration |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

Per-pillar docs live inside each pillar's directory:
- `minxg/ga/README.md` — Geometric Algebra
- `minxg/cat/README.md` — Category Theory
- `minxg/infogeo/README.md` — Information Geometry
- `minxg/topo/README.md` — Algebraic Topology
- `minxg/chaos/README.md` — Dynamical Systems
- `minxg/fiber/README.md` — Fiber Bundles

(Each available in English / 简体中文 / 日本語 / 한국어.)

---

## Verified environments

- **Termux / Android 10+** (this project's primary dev env)
- **Linux x86_64** (Ubuntu 22.04+, Debian 12+)
- **macOS 12+** (Intel and Apple Silicon)

---

## License

MIT
