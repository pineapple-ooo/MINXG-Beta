# DEVELOPER.md — Full developer reference

Everything you need to read, modify, extend, and ship MINXG.

---

## 1. Repository layout

```
.
├── minxg/                         the Python package (canonical import)
│   ├── __init__.py                top-level API + pillar auto-registration
│   ├── base.py                    BaseWorker, ToolDef, WorkerRegistry
│   ├── operators.py               OperatorRegistry — math operator ID space
│   ├── server.py                  HTTP RPC server
│   ├── _config.py                 runtime configuration store
│   ├── five_pillars/              five orthogonal function planes
│   │   ├── scalar/                math, datetime, text, color
│   │   ├── aggregate/             crypto, encoding, ml, templates
│   │   ├── io/                    fs, network, media, web, archive
│   │   ├── dispatch/              system, sh, adb, root, platform
│   │   └── transform/             state, events, rules, persistence
│   ├── contracts/                 Cell / Port / Registry framework
│   ├── driver/                    Temporal Operator-Field driver engine
│   ├── ga/                        Geometric Algebra primitives
│   ├── cat/                       Category Theory operators
│   ├── infogeo/                   Information Geometry operators
│   ├── topo/                      Algebraic Topology operators
│   ├── chaos/                     Dynamical Systems operators
│   └── fiber/                     Fiber Bundle operators
├── py_workers/                    backward-compat alias package (do not edit)
├── multiling/                     orchestration layer
│   ├── agent/                     Multi-agent runtime
│   ├── analytics/                 Rolling-window event tracker
│   ├── auth/                      Token store and RBAC
│   ├── cache/                     LRU and TTL caches
│   ├── config/                    YAML/JSON/TOML/env loader
│   ├── knowledge/                 TF-IDF + prefix knowledge base
│   ├── pipeline/                  Stage-based data pipeline
│   ├── profiler/                  cProfile wrapper with structured output
│   ├── queue/                     FIFO and priority queues
│   ├── scheduler/                 Cron-style job scheduler
│   ├── testing/                   Fixtures, mocks, patch ctx-manager
│   ├── vector/                    In-memory vector store
│   └── workflow/                  DAG-based workflow engine
├── multiligua_cli/                interactive CLI helper
├── extensions/                    extension system
│   ├── builtin/                   built-in extensions (auto-detection)
│   ├── user/                      user-installed extensions
│   ├── import_wizard.py           extension importer
│   ├── loader.py                  extension lifecycle
│   └── zipscan/                   example extension
├── tests/                         pytest suite
├── docs/                          additional documentation
├── go_core/   cpp_core/   c_core/ optional native modules
├── gateway/                        Go HTTP gateway (optional)
├── scripts/
│   └── strip_comments.py          state-machine comment scrubber
├── pyproject.toml
└── README.md
```

The legacy `_legacy/` directory contains old experiments and is gitignore'd
from active development.

---

## 2. Design principles

Every design choice in MINXG flows from three rules.

### Rule 1 — One responsibility per module

Every Python file has a single responsibility and exposes it through a
small public surface. A worker class owns its tools; a pipeline owns its
stages; a registry owns entries. Files don't share mutable state.

### Rule 2 — Edit-one-doesn't-cascade

Replacing or removing a module never forces another module to change.
Three mechanisms enforce this:

* **Absolute imports** across the five pillars — no sibling-module
  imports. Each worker imports `minxg.base` for the worker base class
  and otherwise stands alone.
* **Capability-based dispatch** in `minxg.contracts` — Cells declare what
  they provide; queries match by capability, not by class.
* **Operator registry** in `minxg.operators` — math operator IDs are
  stable; adding new operators never changes existing IDs.

### Rule 3 — Native code is optional

Pure-Python defaults. Native modules in `c_core`, `cpp_core`, `go_core`
speed up hot paths but are detected at runtime. Removing them leaves the
package importable and runnable.

---

## 3. The five pillars

The package layout puts each worker class into one and only one pillar.
Choosing the right pillar for a new worker is mechanical:

| Pillar       | Use when the worker                                  | Examples                       |
|--------------|------------------------------------------------------|--------------------------------|
| scalar       | pure functions over a value, no side effects         | math, datetime, color          |
| aggregate    | bundles values, encodes, transforms bulk data        | crypto, encoding, ml, i18n     |
| io           | the worker crosses the process boundary              | fs, network, web, db           |
| dispatch     | the worker invokes a system or controls another      | sh, adb, process, go bridge    |
| transform    | the worker carries or modifies state                 | events, rules, sessions, ai    |

If a worker fits two pillars, place it in the one closer to where it
*outputs*. Each pillar's `__init__.py` re-exports the public workers.

---

## 4. Worker base class

`minxg.base.BaseWorker` provides:

* `_register_tools()` — call once in `__init__` to wrap `@tool`-decorated
  methods into `ToolDef` entries.
* `tools` — public dict of `name → ToolDef`. Each `ToolDef` carries a
  `description`, a `category`, and the awaitable callable.
* `__call__` and async methods — worker instances are themselves callable
  proxies for testing.

```python
from minxg.base import BaseWorker, tool

class EchoWorker(BaseWorker):
    worker_id = "echo"
    version = "1.0.0"

    @tool(description="Echo back a string.", category="text")
    async def echo(self, message: str) -> dict:
        return {"echo": message}
```

The wrapper `WorkerRegistry.register(worker_instance)` makes the worker
visible to the HTTP RPC layer (`minxg.server`) without changing the
worker.

---

## 5. Driver engine — Temporal Operator-Field

`minxg.driver` is MINXG's self-developed driver architecture. It treats
each operator as a *vector field* on a state manifold and integrates the
state with explicit Euler steps.

### Why this design

Standard task graphs (used by most AI frameworks) call callables in a
fixed order. Swapping two commutative operations still requires
re-writing the graph, the documentation, and the test fixtures.

The driver approach inverts the relationship: a worker is a pure mapping
`State → State`. Conventions like commutativity fall out of the
mathematical structure rather than from explicit ordering directives.
Adding a new worker is a one-line `engine.add_operator(...)` change.

### Core components

| Class          | Role                                                       |
|----------------|------------------------------------------------------------|
| `State`        | Flat `Mapping[str, float]` with optional per-key bounds    |
| `Operator`     | Pure `State → State` mapping                               |
| `Identity`     | Unit operator: returns its input unchanged                 |
| `Composition`  | Two-Operator chain                                         |
| `DriverEngine` | Integration loop, drift control, phase observability       |
| `Field`        | Factory interface for declarative operators                |
| `StepReport`   | Per-step diagnostic record (drift, subdivisions, notes)    |

### Engine integration

```python
from minxg.driver import (
    State, DriverEngine, arithmetic_field,
    parametric_field, smoothing_field, clamp_field,
)

state = State(payload={"x": 0.0, "v": 1.0},
              bounds={"x": (-10.0, 10.0)})

engine = DriverEngine([
    arithmetic_field(lambda s: {"v": 0.1}, name="acceleration"),
    clamp_field(-1.0, 1.0),
    smoothing_field(rate=0.2),
])

end, reports = engine.run(state, n_steps=50)
```

### Phase model

The engine is observable through `EnginePhase`:

```
READY → STEPPING → READY      normal cycle
READY → PAUSED                 user-paused; no-op until reset()
*     → HALTED                 stop and require explicit reset()
*     → FAULTED                unrecoverable; reset before reuse
```

Register a phase listener:

```python
engine.on_phase(lambda prev, new: log.info("%s → %s", prev, new))
```

### Drift control

Each step computes the Euclidean distance between the pre-step State and
the post-step State. If this drift exceeds `max_drift`, the engine
subdivides `dt` up to `max_subdivisions` times before committing. This
keeps chaotic fields stable without forcing developers to hand-tune
step sizes.

---

## 6. Contracts — Cell-Registry-Plugin

`minxg.contracts` formalises the "edit one, rest stays put" property.

```
Cell       — capability-bearing, pluggable unit
Registry   — type-keyed catalogue of Cells
Port       — async boundary a Cell exposes to the outside world
Lifecycle  — BORN → MUTABLE → LIVE → QUIET → GONE
```

### Registering a Cell

```python
from minxg.contracts import get_registry, CellMeta, capability

class PricingCell(metaclass=CellMeta):
    cell_id = "pricing.shipping"
    cell_version = "1.0.0"

    @capability("price.quote")
    def quote(self, weight_kg: float, zone: str) -> dict:
        ...
```

After import, `get_registry().find_by_capability("price.quote")` returns
the registered instance. No central dispatch table to edit; adding a new
Cell adds a new entry, nothing else.

### Port for async I/O

```python
from minxg.contracts import port

@port("weather.lookup")
async def fetch_weather(city: str) -> dict:
    return await some_api(city)

# Caller
from minxg.contracts import Registry, Request
reg = Registry()
reg.register(fetch_weather)  # adapts the Port itself as a Cell-like entry
result = await reg.get("weather.lookup").handler(city="Tokyo")
```

---

## 7. Mathematical pillars

Six sub-packages install math-grounded operator libraries.

| Pillar    | Capacities registered                               |
|-----------|-----------------------------------------------------|
| `ga`      | Geometric product, outer/inner/fat-dot, rotors      |
| `cat`     | Morphisms, functors, monads, Yoneda embedding       |
| `infogeo` | Fisher metric, α-connections, divergences           |
| `topo`    | Simplicial complexes, persistent homology, mapper   |
| `chaos`   | Maps, attractors, Lyapunov spectrum, IFS, fractals  |
| `fiber`   | Bundles, connections, sections, parallel transport  |

Each pillar has an `operators_<pillar>.py` file with an idempotent
`register_<pillar>_operators()` function. The top-level
`minxg.__init__` runs them at import time and exposes
`GA_OPERATORS`, `CAT_OPERATORS`, etc., so tests can assert counts.

Pillar code is **pure Python** — no numpy. All math runs on Termux.

---

## 8. Multiling layer

`multiling/` is orchestration code that uses the `minxg` package as a
library. The sub-modules are deliberately decoupled:

* `agent/` — multi-agent runtime; agents are independent objects with
  role + memory.
* `analytics/tracker.py` — thread-safe rolling event log.
* `auth/tokens.py` — bearer-token issuance and validation.
* `cache/lru.py` — hit/miss-aware LRU.
* `cache/ttl.py` — sliding expiry.
* `config/loader.py` — YAML/JSON/TOML/env layered config.
* `knowledge/base.py` — TF-IDF + prefix-search knowledge base.
* `pipeline/runner.py` — Stage-based pipeline with retry and parallel
  composition.
* `profiler/profile.py` — cProfile wrapper with sync/async decorators.
* `queue/fifo.py` — bounded FIFO with `cv`-based blocking.
* `queue/priority.py` — heap-based priority queue with FIFO tie-break.
* `scheduler/scheduler.py` — interval-based daemon scheduler.
* `testing/fixtures.py` — fixtures, `Mock`, `patch()` ctx-manager.
* `vector/store.py` — cosine / dot / euclidean vector store.
* `workflow/engine.py` — DAG workflow engine with topological execution.

Each sub-module exposes both a class (for embedding) and module-level
singletons for convenient use.

---

## 9. CLI

`multiligua_cli/` provides the interactive terminal. The `update`
subcommand has been removed in v1.1.0; use `pip install --upgrade
minxg` instead.

---

## 10. Tests

```
pytest tests/ -q
```

The suite currently covers:

* `tests/test_01..06_*`  — one file per mathematical pillar
* `tests/test_07_operator_registry.py` — registry idempotency
* `tests/test_08_config.py` — config layering
* `tests/test_09_persistence.py` — alias back-compat
* `tests/test_driver.py` — driver engine invariants
* `tests/test_extensions.py` — extension loader

Total: 75 tests, ~2 seconds on Android.

---

## 11. Pitfalls

* **Termux linker namespace** — `.so` files must live under
  `/data/data/com.termux/files/usr/lib/`. `minxg.five_pillars.scalar.core_native`
  auto-copies a found shared library to that path before `ctypes.CDLL`.
* **Pillar boundary** — never use relative imports across pillars. Use
  the full `minxg.five_pillars.<pillar>.<name>` path even when importing
  a sibling. This makes refactors mechanical.
* **Operator IDs** — the mathematical-pillar operator IDs are stable:
  `5000–5499` for GA, `4000–4499` for CAT. Extensions start at `10000`.
* **`platform.system()`** returns `Android` on Termux, not `Linux`. The
  `minxg.five_pillars.dispatch.platform_registry` already handles this.
* **4-quote strings** — first-run strip_comments may emit `""""` instead
  of `"""`. Run the normaliser `grep -lE '"{4,}|.{4,}'` to detect; the
  fix is `re.sub(r'"{4,}', '"""', src)`.
* **pytest cache** — `.pytest_cache` causes recurring re-runs; not added
  to source.

---

## 12. Publishing checklist

* `pytest -q` returns 75 passed.
* `python -m py_compile $(find . -name '*.py' -not -path '*/_legacy/*')`
  returns 0.
* `python -c 'import minxg; print(minxg.VERSION)'` prints `1.1.0`.
* All five pillar `__init__.py` re-exports match `minxg.__all__`.
* `docs/DRIVER.md`, `docs/PILLARS.md`, `docs/ARCHITECTURE.md` exist and
  match the code.
* No `__pycache__` is committed.
