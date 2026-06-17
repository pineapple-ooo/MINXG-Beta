# ARCHITECTURE

> The full architecture of MINXG — read this when you need the big picture.
> For a one-page map, see [PROJECT_INDEX.md](PROJECT_INDEX.md).

---

## 1 · Layered system

```
┌────────────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                             │
│           (agents, extensions, user code)                      │
├────────────────────────────────────────────────────────────────┤
│                  SELF-EVOLUTION LAYER                          │
│      (behavioral isomorphism, ISG, NCD, 10 algorithms)         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  GA 47 │ CAT 79 │ IG 51 │ TOPO 53 │ CHAOS 23 │ FIBER 53        │
│  ────   ─────   ─────   ───────   ────────   ────────          │
│  six mathematical pillars — see minxg/<pillar>/README.md      │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                  PYTHON OPERATOR REGISTRY                      │
│           376 operators in 11 categories                      │
│  math 20 │ text 19 │ data 12 │ logic 13 │ system 6            │
├────────────────────────────────────────────────────────────────┤
│                  TIDAL LOCK C ACCELERATION                     │
│          c_core/   cpp_core/   go_core/                       │
├────────────────────────────────────────────────────────────────┤
│                  WORKER LAYER                                  │
│        FS · Network · State · Crypto · ML · System            │
├────────────────────────────────────────────────────────────────┤
│                  PLATFORM ADAPTERS                             │
│         Termux · Linux · macOS · iOS · IoT                    │
└────────────────────────────────────────────────────────────────┘
```

## 2 · The six mathematical pillars

### 2.1 Geometric Algebra — `minxg/ga/` — 47 operators

**Clifford Algebra** — unifies scalars, vectors, matrices, quaternions
into a single **multivector** type. The geometric product

  ab = a·b + a∧b

is the only operation. Rotations, reflections, translations, and
dilations are all **versors** acting via the sandwich product x ↦ VxV⁻¹.

Read more: `minxg/ga/README.md`

### 2.2 Category Theory — `minxg/cat/` — 79 operators

Every operator is a **morphism** with explicit domain and codomain.
Composition is type-checked at construction time. Includes:

- 5 **functors** (Identity, Maybe, Either, ListF, Const, Reader)
- 7 **monads** (Identity, Maybe, Either, State, Reader, IO, List)
- **Yoneda embedding** for canonical operator representation
- **Law-verification** operators for functors and monads

Read more: `minxg/cat/README.md`

### 2.3 Information Geometry — `minxg/infogeo/` — 51 operators

Probability distributions form a **Riemannian manifold** with the Fisher
information matrix as the metric. Amari's α-connection generalizes
exponential and mixture connections. The **natural gradient** is
reparameterization-invariant.

Includes KL, JS, Rényi, Bregman, Hellinger, Total Variation divergences.

Read more: `minxg/infogeo/README.md`

### 2.4 Algebraic Topology — `minxg/topo/` — 53 operators

**Topological Data Analysis** primitives:

- Simplicial complexes with Betti number computation
- Persistent homology (H₀, H₁, H₂)
- Vietoris-Rips and alpha-complex filtrations
- Persistence diagrams with Wasserstein distance
- Persistence images for ML
- Mapper algorithm for topological simplification

Read more: `minxg/topo/README.md`

### 2.5 Dynamical Systems & Chaos — `minxg/chaos/` — 23 operators

- **Discrete maps**: logistic, Henon
- **Continuous systems**: Lorenz, Rössler, Duffing (RK4)
- **Lyapunov exponents** (1D and full spectrum)
- **Fractal dimensions**: box-counting, Hausdorff, correlation, Kaplan-Yorke
- **Iterated function systems**: Sierpinski, Koch, Barnsley
- **Bifurcation diagrams** and the Feigenbaum constant

Read more: `minxg/chaos/README.md`

### 2.6 Fiber Bundles — `minxg/fiber/` — 53 operators

The unifying language of gauge theory and modern geometry.

- **Vector and principal bundles**
- **Connections** (Christoffel symbols) with **parallel transport** and **holonomy**
- **Curvature** (Riemann, Ricci, scalar)
- **Sections and covariant derivatives**
- **Tangent bundle** with Levi-Civita connection
- **Geodesics** and **exponential map**
- **Frame bundle** with **vielbein**
- Standard manifolds: Euclidean, sphere, hyperbolic, Minkowski

Read more: `minxg/fiber/README.md`

## 3 · The operator registry

All 376 operators are registered in a single global
`OPERATOR_REGISTRY` in `minxg/operators.py`. The registry supports:

- Lookup by ID, name, or category
- Type-aware composition (for CAT operators)
- Idempotent registration (re-imports are safe)

```python
from minxg.operators import OPERATOR_REGISTRY

op = OPERATOR_REGISTRY.get_by_id(5001)
op = OPERATOR_REGISTRY.get_by_name("cat_list_map")
ops = OPERATOR_REGISTRY.get_category("ga")
```

**ID allocation** — see [PROJECT_INDEX.md](PROJECT_INDEX.md) § 4.

## 4 · Configuration

`config/minxg.yaml` is the single source of truth for runtime config.
Read it via `minxg.get(key)`:

```python
import minxg
print(minxg.get("project.version"))   # 0.0.1a
print(minxg.get("operators.total"))    # 376
print(minxg.get("pillars.0.name"))     # ga
```

## 5 · Acceleration cores

Python is the **single source of truth** for every operator. Native runtimes
sit underneath as drop-in accelerators — never as gates.

### 5.1 Three runtimes, one vocabulary

| Runtime     | Role                                                              | Path         |
|-------------|-------------------------------------------------------------------|--------------|
| `c_core/`   | **Tidal Lock** — 11 locked functions (self-evolution primitives). | `c_core/`    |
| `cpp_core/` | Heavy data processing (CSV, JSON, transforms).                    | `cpp_core/`  |
| `go_core/`  | Network primitives: HTTP gateway, rate limit, WebSocket bridge.   | `go_core/`   |

They are **not interchangeable**. Each runtime owns one concern so that
deprecation of any single one stays tractable.

### 5.2 Offload pattern (uniform across runtimes)

Every worker that may use a native backend follows this idiom (see
`minxg/core_native.py` for the canonical example):

```python
# Module level — soft import, no crash on missing .so
try:
    from . import core_native as _c
    _HAS_NATIVE = _c.ready()
except Exception:
    _HAS_NATIVE = False

@tool
def some_op(...):
    if _HAS_NATIVE:
        try:
            return _c.some_op(...)
        except Exception:
            pass    # fall through to pure Python
    return _pure_python_some_op(...)
```

The rule: **pure Python must always be sufficient**. Native code only
ever speeds up the same observable behaviour.

### 5.3 Android / Termux quirks

- `ctypes.CDLL("/storage/emulated/0/...")` fails with the linker
  namespace restriction. `core_native._find_lib()` auto-copies the
  `.so` to `/data/data/com.termux/files/usr/lib/` before loading.
- `numba` / `cupy` are unavailable. Heavy numeric code (IG/FIBER) is
  pure Python with optional `c_core` acceleration.
- Recommended CFLAGS: `-O2 -ffast-math -shared -fPIC`; recommended
  `-l`: `zstd xxhash orjson`.

### 5.4 When to add a native accelerator

Add a third-tier native only when:

1. Pure-Python profiler shows ≥ 5× speedup is achievable.
2. The semantics are stable (no algorithm in flux).
3. The boundary is already factored (see § 5.2).

Otherwise keep it pure Python — `pytest tests/ -v` on Termux must
stay green.

## 6 · Self-evolution

Above the operator registry sits the **self-evolution engine** in
`src/ai/memory/`. It uses Behavioral Isomorphism (ISG + NCD) to learn
from past interactions. See [SELF_EVOLUTION.md](SELF_EVOLUTION.md).

## 7 · Extension points

Every layer is extensible:

- **New operator**: register in the relevant pillar's `operators_*.py`
- **New worker**: subclass `BaseWorker`, use `@tool` decorator
- **New pillar**: copy `minxg/fiber/`, register in `minxg/__init__.py`
- **New extension**: drop into `extensions/user/`
- **New platform**: implement adapter in `src/platform_adapters/`
- **New translation**: copy `README.md` to `README.<locale>.md`

See [EXTENSIONS.md](EXTENSIONS.md) for details.
