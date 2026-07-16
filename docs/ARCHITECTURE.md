# MINXG Architecture — No Bullshit Edition (v0.18.2)

> Think of this as the "how does this thing actually work?" doc.
> Written for developers who want to ship, not PhDs who want to argue about monads.

---

## What even is MINXG?

MINXG is a polyglot AI agent platform. It runs in Python but has Rust doing the
hot math, C++ guarding memory like a paranoid bouncer, R doing statistics,
Julia JITting the expensive loops, Datalog solving logic puzzles, and WASM/Go
filling in the gaps. The AI gateway is OpenAI-compatible — swap the provider
without rewriting your tools.

---

## The layer cake (bottom to top)

```
┌──────────────────────────────────────────────────────────────┐
│  multiligua_cli / gateway — the stuff users actually see    │
│  (interactive REPL, optional HTTP/WS frontends)             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  multiling/ — the brain: agent, analytics, auth, cache,     │
│  config, knowledge, pipeline, profiler, queue, scheduler,    │
│  testing, vector, workflow                                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  minxg  (the canonical package)                              │
│                                                              │
│  Five pillars:                   Standalone bits:            │
│  ─────────────────              ─────────────────            │
│  scalar/  aggregate/            driver/  (operator-field     │
│  io/      dispatch/               engine — self-cooked)      │
│  transform/                                                 │
│                                contracts/  (Cell-Registry)  │
│  math pillars:                  base.py  (BaseWorker,         │
│  ga/ cat/ infogeo/               ToolDef, WorkerRegistry)   │
│  topo/ chaos/ fiber/           operators.py  (math IDs)     │
│                                server.py  (HTTP RPC)         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  rust_core · cpp_core · go_core — optional native modules   │
│  detected at runtime, no hard deps                          │
└──────────────────────────────────────────────────────────────┘
```

**Rule: each layer only knows about the one directly beneath it.** The i18n
module doesn't know about the gateway. The gateway doesn't know about math
pillars. Mess with one layer, the others don't care.

---

## The five pillars — what each one does

| Pillar | Does | Sounds like |
|--------|------|-------------|
| `scalar` | Math + text ops | the calculator that actually works |
| `aggregate` | Encoding, crypto, ML templates | the guy who formats things and locks doors |
| `io` | FS, network, web | moving data in and out |
| `dispatch` | Shell, ADB, sysadmin stuff | root access without the ego |
| `transform` | AI tools, state sessions | the actual AI glue |

**Pillar rule: imports go only one way.** Siblings don't talk to each other.
Every pillar touches `minxg.base` and nothing else. Add a new pillar? It
plugs in without breaking existing ones.

---

## The math pillars (the overachievers)

Six bundles of mathematical muscle that make the operator registry look like a
weapon shop:

| Pillar | ID range | Sweet spot |
|--------|----------|------------|
| `ga` | 5000–5499 | Geometric algebra: rotors, blades, line intersections |
| `cat` | 4000–4499 | Category theory: morphisms, functors, monads |
| `infogeo` | 7000–7499 | Information geometry: Fisher metric, KL divergence |
| `topo` | 8000–8499 | Algebraic topology: persistent homology, Mapper graphs |
| `chaos` | 8500–8999 | Dynamical systems: maps, attractors, **Lyapunov exponents** |
| `fiber` | 6000–6499 | Fiber bundles: connections, parallel transport |

Each pillar owns its ID range forever. New operators get appended, never
renumbered. Old code keeps working because IDs are permanent.

---

## Driver engine — what it is and when to use it

The driver treats every operation as a **vector field** on a shared state
manifold and shoves the state through explicit Euler steps.

```python
from minxg.driver import (
    State, DriverEngine,
    arithmetic_field, parametric_field, smoothing_field, clamp_field,
)

state = State(payload={"x": 0.0, "v": 1.0}, bounds={"x": (-10.0, 10.0)})

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

**When to reach for this:** your task looks like a sequence of transformations on
shared numeric state, you want order-independence, or the system has drift
sensitivities (chaotic, stiff, multimodal).

**When to use workers directly:** one-shot dispatch, I/O, anything that isn't a
pure state transform.

### Adaptive sub-stepping

Each step computes drift. If drift > `max_drift`, the engine halves `dt` and
retries — up to `max_subdivisions` times. Chaotic fields stay stable even with
a large nominal step size.

---

## Self-evolution loop (v1.2.0)

The engine watches itself fail and asks the network to fix it:

```
 DriverEngine (running)
        │ step()
        ▼
  FailureTour — detects NaN / blown-up amplitude
        │ failures_by_op
        ▼
  FieldForge — asks the contracts registry for cells
        │ advertising the same capability
        ▼
  TwinEngine — shadow clone tests the candidate
        │ TwinOutcome.accepted
        ▼
  replace_operator(idx, op) — swaps the broken one out
```

The loop is **purely advisory.** It never mutates the live engine mid-step.
Replacements land atomically at the end of a cycle, bounded by
`max_replaces_per_cycle` (default: 3).

---

## The contracts / Cell system

Think of it as a **capability marketplace** — no central dispatch table,
no framework tax, no shared mutable state:

```
Cell A ─┐                            ┌─ Cell B
        │     Registry               │
        └──→  registered cells  ◄───┘
              find_by_capability()
              │
              ▼
         "who can quote shipping?"
              │
              ▼
         Registry returns Cell A
         Caller only knows the capability name
```

To add a Cell: define `cell_id`, `cell_version`, decorate methods with
`@capability(...)`, register with `get_registry().register(instance)`.
Done. No YAML, no config files, no boilerplate.

---

## The polyglot runtime

| Language | Job | Why |
|----------|-----|-----|
| **Rust** | Math ops, string ops, hash, dot product, vector peripherals | Speed + memory safety |
| **C++** | Lock-free ring buffer, zero-copy guards | Cache-line correct SPSC |
| **R** | Cold statistics, bootstrapping, time series | CRAN ecosystem |
| **Julia** | JIT-hot loops, numerical PDEs | MATLAB done right |
| **Datalog** | Logic rules, constraint solving | Recursion without the pain |
| **Go** | HTTP services, CLI wrappers | Boring and correct |
| **WASM** | Browser-adjacent compute | Runs anywhere |

Rust core ships as `libminxg_rust.so` (or `.dylib` on Mac). If it isn't built,
MINXG falls back to pure Python. No hard deps.

---

## Tool consolidation (v0.16.5 → now)

Pre-de-dup: ~656 `@tool` methods across 56 workers. Nobody needs 656 tools.

**Fix:** Every legacy worker sets `facade_alias = "<X>"`. `BaseWorker.list_tools`
returns `[]` for them, collapsing the visible surface to ~150-200. Direct callers
(tests, gateway endpoints, imports) keep working unchanged. **Zero breaking
changes.**

---

## Alias map (flat → five-pillar migration)

Old code still works via the compat layer:

| Old flat name | Where it lives now |
|---------------|-------------------|
| `py_workers.fs_io` | `minxg.five_pillars.io.fs_io` |
| `py_workers.system` | `minxg.five_pillars.dispatch.system` |
| `py_workers.ai_tools` | `minxg.five_pillars.transform.ai_tools` |
| `py_workers.crypto_tools` | `minxg.five_pillars.aggregate.crypto_tools` |
| `py_workers.text_tools` | `minxg.five_pillars.scalar.text_tools` |
| `py_workers.ga`, `.cat`, ... | `minxg.ga`, `minxg.cat`, ... (math pillars, unchanged) |

---

## API cheat sheet

| Symbol | Location | What it does |
|--------|----------|--------------|
| `State` | state.py | Numerical payload + bounds |
| `Operator` | operator.py | Base class for vector fields |
| `Identity` | operator.py | `f(x) = x` (does nothing, useful in composition) |
| `Composition` | operator.py | `left ∘ right` — compose operators |
| `DriverEngine` | engine.py | Integration loop |
| `StepReport` | engine.py | Per-step diagnostics (drift, subdivisions, notes) |
| `EnginePhase` | engine.py | READY / STEPPING / PAUSED / HALTED / FAULTED |
| `arithmetic_field` | fields.py | `State → delta dict` factory |
| `parametric_field` | fields.py | Linear gain on one axis |
| `clamp_field` | fields.py | Hard bounds on every payload key |
| `smoothing_field` | fields.py | Exponential decay toward a target |
| `lyapunov_logistic` | rust_bridge.py | λ > 0 = chaos, λ < 0 = periodic (Rosenstein method) |
| `fixed_point_iter` | rust_bridge.py | Solve x = g(x) by successive substitution |

---

## How not to break things

Three rules make MINXG mechanically refactorable:

1. **No relative imports across pillars.** `scalar/math.py` changing can't break
   `io/network.py` because `io/network.py` doesn't import it.
2. **Capability-based dispatch.** Cells advertise what they do; nobody imports
   the class directly.
3. **Stable operator IDs in `minxg.operators`.** Math IDs are declared once and
   never renumbered.

---

*Last updated: v0.18.2*
*Questions? Fix the code and send a PR.*