# DEVELOPER.md — Full developer reference

Everything you need to read, modify, extend, and ship MINXG.

---

## 0. v0.13.0 release notes (2026-06-25) - Surface sweep + experimental verbs

A focused cleanup that:

  - **Promotes eight subsystem modules to the top level.** `minxg.twin`,
    `minxg.lens`, `minxg.lossless`, `minxg.self_evolution`,
    `minxg.polyglot`, `minxg.driver`, `minxg.cap`, and `minxg.contracts`
    are now attributes of the top-level `minxg` package — so
    `import minxg; minxg.twin` works the same way as `import minxg;
    minxg.ga`. `from minxg.<x> import ...` continues to work as before.
  - **Removes the stale `docs/archive/` folder (10 files).** Includes the
    obsolete multi-AI negotiation file (`docs/archive/AGENTS.md`) that
    used to inject anti-loop directives into AI system prompts; that
    mechanism is no longer needed and the file would only confuse future
    AI contributors. Key bug fixes/pointers previously archived are now
    reflected inline in DEVELOPER.md and README.md.
  - **Adds five new experimental CLI verbs** under
    `multiligua_cli/experimental.py`:
    - `minxg bench` — local perf snapshot of `lossless`, `driver`,
      `twin`, `polyglot`, `operators`, and the experimental import path.
    - `minxg replay <file>` — re-render an exported markdown chat log.
    - `minxg theme [dark|colorful|minimal]` — get/set the active TUI
      theme; state lives in `~/.minxg/theme.json`.
    - `minxg safe-eval <expr>` — restricted arithmetic evaluator
      (allowed-builtins-only, no attribute access, no comprehensions).
    - `minxg ext-reload --all` — rescan extension sources without
      restarting the interpreter.
    Every experimental verb prints an
    `[EXPERIMENTAL] minxg <verb> — signature may change`
    banner so users always know what they're getting into. The five
    verbs are exercised by `tests/test_experimental_cli.py` (added in
    this release) so a regression that breaks the dispatch path breaks
    CI.
  - **Documents the operator registry at runtime.** README §Mathematical
    pillars no longer references a phantom `docs/OPERATORS.md` file —
    the canonical truth lives in `minxg.operators.OPERATOR_REGISTRY`,
    which now exposes `total_operators` (376) and `list_categories()`
    (11 categories). A 4-line snippet replaces the dead link.
  - **Locks the ID-range claim to ground truth.** The `ga` pillar range
    in README was previously claimed as `5000-5049` but the registered
    IDs end at `5046`; corrected to `5000-5046`. Other ranges were
    already accurate.

## 0. v0.14.0 release notes (2026-06-27) - Polyglot expansion + gateway hardening

Lead with a one-line summary, then list the changes. The exact set will be
filled in when 0.14.0 ships; the ``Version:`` line below is what
``tests/test_version_lock.py`` reads to enforce cross-surface parity.

**Cross-cutting variables to keep in sync when forking:**
- `minxg/_version.py:VERSION` — **single source of truth**.
- `pyproject.toml` reads the version from the SSoT via setuptools dynamic.
- `minxg/__init__.__version__` imports `from ._version import VERSION`.
- `config/minxg.yaml:project.version` (if present).
- `install.sh` brand echo + cheatsheet.
- `README.md` ¶ "v0.X.Y release" highlight.
- `CHANGELOG.md` top section.

Version: 0.14.0

If any of these drift, `minxg doctor` and the `tests/test_version_lock.py`
test will fire. Now `413 + 1 skipped` v0.12.5 baseline expands to
`>= 470` in this release.

---

## 0a. Historical — v0.11.0 release notes (2026-06-19)

Cold-start hardening. No breaking-API changes; same `minxg` imports,
same worker count, same operator registry.

  - **Built-in extensions are now opt-in.** The legacy
    `ADB_AVAILABLE` / `ROOT_AVAILABLE` auto-detect ladder is gone;
    each built-in ships with `EXTENSION_ENABLED = False`. Opt-in via
    `minxg ext add <slug>`, which writes
    `extensions/user/<slug>.state`. This is the structural fix for
    pitfalls 31 and 34 in `minxg-megarefactor-v1`.
  - **`minxg doctor` ships.** `multiligua_cli/doctor.py` is a new
    self-check sub-command with a POSIX exit-code contract
    (0 OK, 1 fail, 2 warn) so users can wire it into startup scripts
    and bug-report templates.
  - **cpp_core build link error fixed.** `cpp_core/CMakeLists.txt`
    now also links `c_core/text_engine.c` into `libminxg_core.so`,
    so the dlopen error `cannot locate symbol "minxg_slugify"`
    no longer fires on a fresh Termux install. Verified at runtime:
    `core_native.sha256(b"hi")` returns the expected hash.
  - **`py_workers` alias hardened.** Pillar aliases
    (`scalar`, `io`, `aggregate`, `dispatch`, `transform`) and the
    six math pillars (`ga`, `cat`, `infogeo`, `topo`, `chaos`,
    `fiber`) all resolve via the alias module's own `__getattr__`.
  - **`install.sh` English-only.** Stripped 43 `[CN]` placeholder
    markers. Brand line is `MINXG v0.11.0`.

Cross-cutting variables to keep in sync when forking:

  - `minxg.VERSION` (single source of truth).
  - `pyproject.toml:version`.
  - `config/minxg.yaml:project.version`.
  - `install.sh` brand echo + cheatsheet.

If one of these drifts, run `minxg doctor` and check that `ai.base_url`
plus the four `--version` surfaces are still pointing at one number.

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
├── minxg/                         v1.2.0 self-developed subsystems
│   ├── contracts/                 Cell / Port / Registry framework (edit isolation)
│   ├── driver/                    Temporal Operator-Field driver engine
│   ├── self_evolution/            closed-loop self-improvement on driver drift
│   ├── polyglot/                  multi-language source-to-graph normaliser (Python ast + 4-lang regex heuristics)
│   ├── lossless/                  BIE-geometry byte-identical round-trip (CRC-32 trailer, not a zstd competitor)
│   ├── twin/                      Python ↔ Rust RTL emitter
│   └── lens/                      reverse-docstring export to 5 languages
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
subcommand has been removed in v0.11.0; use `pip install --upgrade
minxg-beta` instead.

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
* `tests/test_cap.py` · `test_lens.py` · `test_lossless.py` ·
  `test_polyglot.py` · `test_self_evolution.py` · `test_twin.py`

Total: 130 passed + 1 skipped (no rustc on Termux), ~1.5 s on
Android (Python 3.13).

---

## 11. Pitfalls

* **Termux linker namespace** — `.so` files must live under
  `/data/data/com.termux/files/usr/lib/`. `minxg.five_pillars.scalar.core_native._find_lib()`
  auto-copies a found shared library to that path before `ctypes.CDLL`.
  The search starts at the project root (the directory containing
  `pyproject.toml`) and tries `cpp_core/build/`, then `cpp_core/`,
  then `build/`, in that order. If no candidate matches, the loader
  raises an explicit `OSError` rather than letting `ctypes.CDLL` emit
  a misleading `dlopen failed` against an un-discovered bare name.
* **Pillar boundary** — never use relative imports across pillars. Use
  the full `minxg.five_pillars.<pillar>.<name>` path even when importing
  a sibling. This makes refactors mechanical.
* **Operator IDs** — each mathematical-pillar operator lives in a
  disjoint numeric range. Current ranges:
  `5000-5049` for GA, `4000-4078` for CAT, `7000-7050` for IG,
  `8000-8052` for TOPO, `8500-8522` for CHAOS, `6000-6052` for FIBER.
  Outside these pillars: `0-19` math, `2000-2018` text, `3500-3511`
  data, `5500-5512` logic, `9000-9005` system. Source of truth is
  `config/minxg.yaml` § `operators.categories.*.id_range`. Extensions
  start at `10000`.
* **`platform.system()`** returns `Android` on Termux, not `Linux`. The
  `minxg.five_pillars.dispatch.platform_registry` already handles this.
* **4-quote strings** — first-run strip_comments may emit `""""` instead
  of `"""`. Run the normaliser `grep -lE '"{4,}|.{4,}'` to detect; the
  fix is `re.sub(r'"{4,}', '"""', src)`.
* **pytest cache** — `.pytest_cache` causes recurring re-runs; not added
  to source.

---

## 12. Publishing checklist

* `pytest -q` returns the current count (≥ 470 passed in this release;
  historical chain 196 → 413 → ≥ 470 across 0.12.0/0.12.5/0.14.0).
* `python -m py_compile $(find . -name '*.py' -not -path '*/_legacy/*')`
  returns 0.
* `python -c 'import minxg; print(minxg.VERSION)'` prints `0.14.0`.
* All five pillar `__init__.py` re-exports match `minxg.__all__`.
* The eight subsystem modules
  (`minxg.{twin,lens,lossless,self_evolution,polyglot,driver,cap,contracts}`)
  are reachable both via `from minxg.<x> import …` **and** via the
  top-level attribute (`import minxg; minxg.twin`).
* `docs/DRIVER.md`, `docs/PILLARS.md`, `docs/ARCHITECTURE.md` exist and
  match the code.
* No `__pycache__` is committed.


---

## 13. v1.2.0 — Self-Developed Subsystems

Five new sub-packages ship on top of the driver engine and the
contracts registry. Each is small (~200-400 LOC) and tightly tested.
None of them is a rebrand of an existing library — they all use the
driver's drift telemetry as their feedback signal.

### 13.1 `minxg/self_evolution`

Closed-loop self-improvement. Four pieces:

* `FailureTour.detect_from_state(step, payload, caused_by)` records
  unrecoverable failures by operator.
* `FieldForge.propose(failures_by_op, probe, n_steps)` queries the
  contracts registry for Cells advertising the same capability as
  the failing operator, measures drift on a synthetic probe, and
  emits ranked `FieldProposal`s.
* `TwinEngine.compare(live_engine, candidate, target_idx, probe,
  tolerance)` runs a shadow clone of the live driver with one
  candidate operator swapped, compares drift, returns `TwinOutcome`.
* `EvolutionLoop.cycle(config)` orchestrates a full cycle. A cycle
  replaces operators whose candidates pass the twin gate and leaves
  the rest.

The loop depends ONLY on the public driver API. It never reaches
into engine internals. Editing `engine.step()` never breaks
self-evolution.

### 13.2 `minxg/polyglot`

Multi-language source-to-graph normaliser. Output is a single
`OperatorGraph` shape regardless of source language. **Python uses
real `ast`; Rust / JavaScript / Go / shell use regex-based structural
heuristics.** Good for code-shape recognition, not a compiler front-end.

```python
from minxg.polyglot import normalize

graph = normalize(source_string)  # auto-detects Python/Rust/JS/Go/shell
for node in graph.topological_order():
    print(node.op_id, "->", node.output)
```

`detect_language(text)` uses regex heuristics; pass `language=`
explicitly to skip detection.

### 13.3 `minxg/lossless`

BIE-geometry byte-identical round-trip. Each byte becomes a unit-sphere
point in (theta, phi); transitions between bytes are blades kept or
dropped based on a curvature threshold. Reconstruction is guaranteed
byte-identical by a CRC-32 trailer. Note: the encoded form is
typically *larger* than the input on real-world data; this is not a
competitor to zstd/gzip.

```python
from minxg.lossless import LosslessCodec

codec = LosslessCodec(curvature_threshold=0.05)
blob = codec.compress(b"hello world") .payload
assert codec.decompress(blob) == b"hello world"
```

Run-length semantics: `SkeletonEntry.run_length` counts how many
times the *previous dst_byte* is repeated before this entry's
dst_byte appears. `run_length=0` is valid for the first transition.

Format header is 11 bytes: magic(b"MINSKE" → 6 bytes), version
(u8), length(u32 big-endian). Round-trip the codec immediately
after writing it — bytes-only I/O bugs hide.

### 13.4 `minxg/twin`

Python ↔ Rust RTL emitter, no compilation dependencies.

```python
from minxg.twin import python_to_rust, rust_to_python

src = python_to_rust('''
    def total(n: int) -> int:
        s = 0
        for i in range(n):
            s = s + i
        return s
''').source
# src is a valid Rust *function* (no module wrapper)
```

Covers: function defs with annotations, while, for-range, if /
elif / else, augmented assignments, bool / binop / compare /
unary expressions, nested if-inside-orelse chains.

Anything else raises `UnsupportedTwinOp(op_name, hint)`. The class
name is exported via `minxg.TWIN_ERROR = "UnsupportedTwinOp"` so
callers can `except minxg.UnsupportedTwinOp: ...` indirectly.

### 13.5 `minxg/lens`

Reverse docstring export.

```python
from minxg.lens import Lens, LensConfig

batch = Lens(LensConfig(languages=("en", "zh"), output_dir=tmp)).render_doc(
    "", {"heading": "operator", "body": "advances the state"},
)
# writes tmp/en.md, tmp/zh.md, tmp/GLOSSARY.md
```

The bundled glossary has 14 entries (operator / driver / bridge /
registry / cell / port / field / state / drift / blade / curvature /
worker / twin / evolution). Add at runtime with
`glossary.add(Entry(term="...", translations={...}))`.

### 13.6 Driver public API dependence

The driver engine deliberately exposes four getters so that
self-evolution / twin / future orchestrators can compose without
reaching into internals:

```python
engine.operators()           -> Tuple[Operator, ...]
engine.step_size()           -> float
engine.max_subdivisions()    -> int
engine.replace_operator(i, op)
engine.remove_operator(name) -> bool
engine.add_operator(op)
engine.on_phase(lambda prev, new: ...)
engine.reset()
engine.halt()
```

Do NOT add private attributes that you intend consumers to read.
Compose through these.

---

## 14. Removing a Published Subsystem

The GitHub `hot-reload` cycle (`git fetch && git reset --hard && pip
install -e .`) was removed in v0.11.0. The lesson is in
`docs/ARCHITECTURE.md` and `minxg-megarefactor-v1/references/`.
When a feature has shipped publicly and you decide it is wrong:

1. `git rm <module>` — don't keep `.disabled` stubs.
2. Sweep `from .X import`, `X.func`, and CLI command shortcuts.
3. Replace each entry with a no-op `print_warning(...) + return 0`
   so wiring stays intact.
4. Sweep `setup.py` prompts and display strings.
5. Run the full py_compile + pytest gate.
6. Commit.

The principle: removing a feature is a one-way door. Make sure
your not-removed callers still type-check and run.
