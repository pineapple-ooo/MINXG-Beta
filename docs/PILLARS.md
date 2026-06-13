# Mathematical Pillars

MINXG bundles six math-pillar sub-packages. Each contributes hundreds
of stable operator IDs to the operator registry.

| Pillar    | Sub-package | ID range | What it offers                                    |
|-----------|-------------|----------|---------------------------------------------------|
| ga        | minxg.ga      | 5000–5499 | geometric algebra: multivectors, blades, rotors  |
| cat       | minxg.cat     | 4000–4499 | category theory: morphisms, functors, monads    |
| infogeo   | minxg.infogeo | 7000–7499 | information geometry: Fisher metric, divergence |
| topo      | minxg.topo    | 8000–8499 | algebraic topology: persistence, mapper         |
| chaos     | minxg.chaos   | 8500–8999 | dynamical systems: maps, attractors, fractals    |
| fiber     | minxg.fiber   | 6000–6499 | fiber bundles: connections, sections            |

## Usage

```python
import minxg
print(minxg.GA_OPERATORS, minxg.CAT_OPERATORS, minxg.IG_OPERATORS,
      minxg.TOPO_OPERATORS, minxg.CHAOS_OPERATORS, minxg.FIBER_OPERATORS)
```

Each pillar re-exports the core classes through its own `__init__.py`:

```python
from minxg.ga import Multivector
from minxg.cat import Morphism, Functor
from minxg.infogeo import Manifold
```

## Why six pillars

The pillars were chosen because each one represents a self-contained
mathematical structure that augments an agent without coupling to the
others:

* **Geometric Algebra** organises spatial reasoning (rotations,
  reflections, line/plane intersections) without floating-point matrix
  arithmetic.
* **Category Theory** provides composition primitives (morphisms,
  monads, functors) that are dual to function composition in code.
* **Information Geometry** maps statistical models onto a curved
  manifold where distance is calibrated to distinguishability (Fisher
  metric, alpha-connections).
* **Algebraic Topology** classifies the *shape* of point clouds via
  persistent homology and the Mapper algorithm.
* **Dynamical Systems** captures iteration, attractors, and Lyapunov
  exponents — the mathematical foundation of recursive generative
  systems.
* **Fiber Bundles** encode how one space varies over another (sections,
  connections, parallel transport).

## Stability guarantees

Operator IDs assigned by these pillars are stable across releases.
Removing or rewriting the implementation of a registered operator does
not change the ID it occupies, so existing call sites continue to
resolve. New operators within a pillar receive the next free ID in the
pillar's reserved range.

## Pillar configuration knobs

Each pillar reads `pyproject.toml` for any mandatory configuration at
import time. None require external services; all compute in-process.
