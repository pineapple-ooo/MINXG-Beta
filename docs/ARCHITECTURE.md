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
