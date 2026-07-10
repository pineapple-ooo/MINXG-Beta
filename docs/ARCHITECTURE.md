# MINXG Architecture (v0.16.5)

Auto-merged from legacy ARCHITECTURE / DRIVER / PILLARS docs at the start of v0.16.5 development. Single source of truth for design.

---

## Architecture (legacy)

# Architecture

Visual map of MINXG. Read this top-down before editing.

## Layer cake

```
┌────────────────────────────────────────────────────────────────────┐
│                       multiligua_cli / gateway                      │
│        (interactive CLI, optional external HTTP/WS frontends)       │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                           multiling/                                │
│  agent · analytics · auth · cache · config · knowledge · pipeline · │
│  profiler · queue · scheduler · testing · vector · workflow        │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                        minxg  (canonical)                           │
│                                                                     │
│   five-pillar layout:               standalone subsystems:           │
│   ─────────────────────             ─────────────────────           │
│   scalar/aggregate/io/              driver/   (operator-field       │
│   dispatch/transform                  driver engine, self-developed)|
│                                                                     │
│                                     contracts/  (Cell-Registry)     │
│                                                                     │
│   ga/ cat/ infogeo/ topo/ chaos/     base.py  (worker base class)   │
│   fiber/                             operators.py  (math IDs)       │
│                                     server.py  (HTTP RPC)          │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│   c_core · cpp_core · go_core         (optional native modules,     │
│                                        detected at runtime)         │
└────────────────────────────────────────────────────────────────────┘
```

Every layer depends only on the layer beneath it. The `minxg` layer
itself is internally split into pillar boundaries that share nothing
except `base.py` and `operators.py`.

## Pillar boundaries

```
                ┌───────────────────────────────┐
                │            base.py            │
                │     BaseWorker, ToolDef,      │
                │     WorkerRegistry            │
                └───────────────────────────────┘
                            ▲   ▲  ▲  ▲  ▲
                            │   │  │  │  │
    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  scalar  │   │ aggregate │  │    io    │  │ dispatch │  │transform │
    │ math.txt │   │encod.crypto│  │ fs.web  │  │ sh.adb   │  │ state    │
    │  dt.text │   │ ml.tmpl    │  │ network │  │ sys.root │  │ sessions │
    └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
        △              △               △              △              △
        └──────────────┴───────────────┴──────────────┴──────────────┘
                            no imports across pillars
```

Pillars import only `minxg.base`. Within a pillar, sibling imports are
fine.

## Driver engine flow

```
  start: State(payload={...}, bounds={...}, timestamp=0)
                    │
                    ▼
  step(state):
      ├─ snapshot state
      ├─ for op in operators:
      │     candidate = op(state)
      │     delta    = candidate - state
      │     state     = state + (dt × delta)   ← explicit Euler
      ├─ drift = ‖state − start‖
      ├─ if drift > max_drift: subdivide dt (≤ max_subdivisions)
      └─ return state, StepReport

  ───────────────────────────────────────────────────────────
  Operator lifecycle (independent of engine code):
      workers import nothing of each other
      operators are pure State → State
      order-independence is a property of the field composition
      swap an Operator → nothing else recompiles
```

## Module independence contract

The `minxg.contracts` module enforces what the layout makes possible:

```
Cell A ─┐                            ┌─ Cell B
        │     Registry                │
        └──→   registered cells   ◄───┘
              find_by_capability()
              │
              ▼
            Caller asks "who can quote shipping?"
            Registry returns Cell A
            Caller's only knowledge of A is the capability name
```

A new Cell:

1. Defines `cell_id`, `cell_version`.
2. Decorates its public methods with `@capability(...)`.
3. Registers itself with `get_registry().register(instance)`.

No central dispatch table, no framework boilerplate, no shared mutable
state.

## Anti-Stampede: edit-one-doesn't-cascade

Three structural mechanisms prevent the typical "I changed one module
and three others broke" pathology:

1. **No relative imports across pillars.** A change to `scalar/math.py`
   cannot break `io/network.py` because the latter does not name it.
2. **Capability-based dispatch.** Cells and operators advertise what
   they do; nobody imports their class.
3. **Stable operator IDs in `minxg.operators`.** Math operator IDs are
   declared once; new operations are appended, never renumbered.

Combined, these make the codebase mechanically refactorable.

## Why mathematical pillars

Six math libraries are bundled because they give the OperatorRegistry a
self-extending skill set. The implementer is not required to think in
math; AI agents can request a still-stable ID range (e.g.
`op:5123 = blade.outer`) and the engine responds.

* `ga` — geometric algebra gives line/plane/rotor operations that map
  cleanly onto physical-space reasoning.
* `cat` — categorical morphisms + monads formalise composability.
* `infogeo` — Fisher Metric / KL divergence are grounded estimation
  tools.
* `topo` — persistent homology classifies shape of data; mapper
  produces graph summaries.
* `chaos` — maps, attractors, fractals parameterise deterministic
  generative systems.
* `fiber` — connection / parallel-transport encode state-in-space
  relations.

Each pillar is isolated, registers idempotently, and never reaches into
its siblings.


## Self-evolution loop (v1.2.0)

```
                  ┌───────────────────────────┐
                  │  DriverEngine (live)      │
                  │  operators = [...]        │
                  └─────────────┬─────────────┘
                                │ step()
                                ▼
                  ┌───────────────────────────┐
                  │  FailureTour              │
                  │  detect NaN / huge amp    │
                  └─────────────┬─────────────┘
                                │ failures_by_op
                                ▼
                  ┌───────────────────────────┐
                  │  FieldForge               │
                  │  queries contracts registry│
                  │  for Cells advertising    │
                  │  same capability          │
                  └─────────────┬─────────────┘
                                │ FieldProposal[]
                                ▼
                  ┌───────────────────────────┐
                  │  TwinEngine               │
                  │  shadow clone engine      │
                  │  compares drift on probe  │
                  └─────────────┬─────────────┘
                                │ TwinOutcome.accepted
                                ▼
                  ┌───────────────────────────┐
                  │  replace_operator(idx, op)│
                  │  - or -                   │
                  │  leave rejected for next  │
                  │  cycle                    │
                  └───────────────────────────┘
```

The loop is purely advisory. It never modifies the live engine
in place during a step; all replacements land at the end of a
cycle. Replacing the live engine is the single mutation per
cycle, bounded by `max_replaces_per_cycle` (default 3).

## Compatibility alias map

The `py_workers/` alias package uses `__getattr__` to map every
flat module name onto its `minxg.five_pillars.<pillar>.<mod>` home.
The flat name stays callable so historical code keeps loading.

| Flat (legacy)                                  | Five-pillar home                          |
|------------------------------------------------|-------------------------------------------|
| `py_workers.fs_io`                             | `minxg.five_pillars.io.fs_io`             |
| `py_workers.system`                            | `minxg.five_pillars.dispatch.system`      |
| `py_workers.ai_tools`                          | `minxg.five_pillars.transform.ai_tools`   |
| `py_workers.crypto_tools`                      | `minxg.five_pillars.aggregate.crypto_tools` |
| `py_workers.text_tools`                        | `minxg.five_pillars.scalar.text_tools`    |
| `py_workers.ga`, `.cat`, ...                   | `minxg.ga`, `minxg.cat`, ... (math pillars, unchanged names) |

Add a new entry to `py_workers/__init__.py`'s `_PILLAR_MODULE_SET`
or `_MATH_PILLARS` when introducing new modules; the alias falls
through to the underlying object via `getattr(minxg, attr)`.


## Driver engine (legacy)

MINXG Driver Engine


The driver engine treats each operation as a vector field on a shared
state manifold and integrates the state through explicit Euler steps.

## When to use the driver

Reach for the driver when your task looks like a sequence of related
transformations on a shared numeric state, especially when:

* you want order-independence (commuting operations never break each
  other)
* you want to add/remove a transformation without rewriting tests
* the system has drift sensitivities (chaotic, stiff, multimodal)

For one-shot dispatch use `minxg.base` workers directly.

## Building an engine

```python
from minxg.driver import (
    State, DriverEngine, arithmetic_field,
    parametric_field, smoothing_field, clamp_field,
)

state = State(
    payload={"x": 0.0, "v": 1.0},
    bounds={"x": (-10.0, 10.0)},
)

engine = DriverEngine(
    [
        arithmetic_field(lambda s: {"v": 0.1}, name="acceleration"),
        clamp_field(-1.0, 1.0),
        smoothing_field(rate=0.2),
    ],
    step_size=0.5,
    max_drift=1.0,
    max_subdivisions=4,
)

new_state, report = engine.step(state)
```

`StepReport` returns:

* `step`: monotonic step counter
* `timestamp`: post-step time
* `drift`: Euclidean distance between start and end states
* `subdivisions`: how many times the engine halved `dt` to keep drift in
  bounds
* `operator_count`: number of operators in this engine
* `notes`: human-readable phase observations

## Adaptive sub-stepping

Each step computes drift. If drift exceeds `max_drift`, the engine
halves `dt` and retries, up to `max_subdivisions` times. This means
chaotic fields stay stable even with a large nominal `step_size`.

## Hooking phase changes

```python
from minxg.driver import EnginePhase

engine.on_phase(lambda prev, new: log.info("%s → %s", prev, new))
```

Phases:

* `READY`    – accepting work
* `STEPPING` – mid-step
* `PAUSED`   – user-requested pause; `step()` is a no-op
* `HALTED`   – stop until `reset()`
* `FAULTED`  – unrecoverable error; `reset()` then resume

## Removing and replacing operators

```python
engine.remove_operator("acceleration")
engine.replace_operator(0, parametric_field("new_a", 0.05, "x"))
```

No state is invalidated, no other engine is affected. The registry hot
swap is the leverage that lets you repurpose a running engine for A/B
testing without restarting.

## Custom operators

```python
from minxg.driver import Operator
from minxg.driver.state import State

class DriftToward(Operator):
    name = "drift_toward"

    def __init__(self, target: dict, rate: float = 0.1):
        self.target = target
        self.rate = rate

    def apply(self, state: State) -> State:
        out = state.clone()
        for k, v in self.target.items():
            current = out.payload.get(k, 0.0)
            out.payload[k] = current + (v - current) * self.rate
        return out

engine.add_operator(DriftToward({"x": 5.0}, rate=0.25))
```

## Combination with workers

Operators are pure-Python, no I/O. To mix a worker into a driver, wrap
its async method:

```python
import asyncio
from minxg.driver import Operator, State

class WorkerOperator(Operator):
    name = "fsworker.read"

    def __init__(self, instance, method: str):
        self.instance = instance
        self.method = method

    def apply(self, state: State) -> State:
        out = state.clone()
        method = getattr(self.instance, self.method)
        result = asyncio.run(method(**out.payload))
        out.payload["last_result"] = hash(tuple(sorted(result.items())))
        return out
```

This is the bridge between the worker system and the driver — and it
inherits the operator's pure semantics, so swapping a worker still
doesn't break other operators.

## API summary

| Symbol            | Where            | Notes                          |
|-------------------|------------------|--------------------------------|
| `State`           | state.py         | Numerical payload + bounds     |
| `Operator`        | operator.py      | Base class for fields          |
| `Identity`        | operator.py      | `f(x) = x`                     |
| `Composition`     | operator.py      | `left ∘ right`                 |
| `DriverEngine`    | engine.py        | Integration loop               |
| `StepReport`      | engine.py        | Per-step diagnostic            |
| `EnginePhase`     | engine.py        | Phase enum                     |
| `Field`           | fields.py        | Operator factory base          |
| `arithmetic_field`| fields.py        | `State → delta dict`           |
| `parametric_field`| fields.py        | Linear gain on one axis        |
| `clamp_field`     | fields.py        | Hard bounds on every key       |
| `smoothing_field` | fields.py        | Exponential decay              |


## v1.2.0 additions

The driver now exposes four public getters used by self-evolution
and any future orchestrator. Use these instead of reaching into
engine internals:

```python
engine.operators()           -> Tuple[Operator, ...]
engine.step_size()           -> float
engine.max_subdivisions()    -> int
```

The phase enumerator is exposed through `from minxg.driver import
EnginePhase` and printed by the bundled `engine.phase` property.

Hook into phase transitions with:

```python
engine.on_phase(lambda prev, new: ...)
```


## Pillars (legacy)

## Mathematical Pillars

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


## Tool consolidation (v0.16.5)

* 56 workers exposed ~656 `@tool` methods pre-v0.16.5. After de-dup
* every legacy worker sets `facade_alias = "<X>"`. `BaseWorker.list_tools`
* returns `[]` for them, collapsing the visible surface to **~150-200**.
* Direct callers (tests, gateway endpoints, imports) keep working
* unchanged so the de-dup is **non-breaking**.

## Polyglot runtime

* Rust core (`rust_core/`) handles math ops, string ops,
* `str_hash64`, dot product, parallel map-reduce, vector peripherals.
* polyglot workers are registered in `five_pillars/polyglot/`.
* `multiligua_cli/experimental.py` exposes the runtime-install verbs.
