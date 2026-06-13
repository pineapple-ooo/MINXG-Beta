# PROJECT_INDEX

> One page to find anything in MINXG.
> Keep this file authoritative — when you add/move/rename things, update the index.

---

## 0 · What is MINXG?

MINXG is a pure-Python AI orchestration framework whose operator set is
grounded in **six mathematical pillars** that no other AI framework
exposes as first-class primitives:

1. **Geometric Algebra** (Clifford) — multivectors, rotors, reflections
2. **Category Theory** — morphisms, functors, monads, Yoneda
3. **Information Geometry** — Fisher metric, natural gradient
4. **Algebraic Topology** — persistent homology, simplicial complexes
5. **Dynamical Systems & Chaos** — Lyapunov, attractors, fractals
6. **Fiber Bundles** — connections, parallel transport, curvature

**376 operators · 11 categories · 6 mathematical pillars · 100% pure Python.**

---

## 1 · Where is everything?

```
MINXG/
├── minxg/                   ← THE Python package (rename of old py_workers)
│   ├── __init__.py          ← single import entry; re-exports everything
│   ├── _config.py           ← loads config/minxg.yaml
│   ├── operators.py         ← single registry for all 376 operators
│   ├── base.py              ← BaseWorker + @tool decorator
│   ├── ga/                  ← pillar 1: Geometric Algebra (47 ops)
│   ├── cat/                 ← pillar 2: Category Theory (79 ops)
│   ├── infogeo/             ← pillar 3: Information Geometry (51 ops)
│   ├── topo/                ← pillar 4: Algebraic Topology (53 ops)
│   ├── chaos/               ← pillar 5: Dynamical Systems (23 ops)
│   ├── fiber/               ← pillar 6: Fiber Bundles (53 ops)
│   ├── ai/                  ← model registry, memory, safety
│   ├── gateway/             ← HTTP / WebSocket API
│   ├── tools/               ← built-in tool workers
│   └── *.py                 ← 50+ tool workers
├── py_workers/              ← BACKWARD-COMPAT ALIAS of minxg
├── config/
│   └── minxg.yaml           ← SINGLE source of truth for runtime config
├── extensions/              ← user/builtin extensions
├── c_core/  cpp_core/  go_core/   ← native acceleration
├── src/                     ← legacy src tree (gateway/ai/security/...)
├── multiligua_cli/          ← CLI entry
├── multiling/               ← legacy 12 utility packages
├── var/                     ← runtime data (logs, cache, sessions)
├── assets/  config/  docs-templates/  go_core/cmd/  scripts/  skills/  tests/
├── pyproject.toml           ← project metadata
├── ARCHITECTURE.md          ← project architecture (you are here)
├── INSTALL.md               ← installation
├── QUICKSTART.md            ← 5-minute tour
├── OPERATORS.md             ← all 376 operators
├── EXTENSIONS.md            ← build your own
├── SELF_EVOLUTION.md        ← the 10 behavioral algorithms
├── TIDAL_LOCK.md            ← C/C++ acceleration
├── CHANGELOG.md             ← version history
├── AGENTS.md                ← AI agent system prompt (legacy)
└── README.md + .zh.md + .ja.md + .ko.md + .zh-TW.md
```

**If you can't find something, search the regex in the operators list
(OPERATORS.md) or in the in-package README (each pillar has one).**

---

## 2 · The 6 Mathematical Pillars — quick index

| Pillar | Code | Operators | What it solves |
|--------|------|-----------|----------------|
| **GA** Geometric Algebra | `minxg/ga/` | 47 | One type for rotations/reflections/dilations |
| **CAT** Category Theory | `minxg/cat/` | 79 | Type-checked composition, monadic side effects |
| **IG** Information Geometry | `minxg/infogeo/` | 51 | Reparameterization-invariant optimization |
| **TOPO** Algebraic Topology | `minxg/topo/` | 53 | Persistent homology, Betti numbers |
| **CHAOS** Dynamical Systems | `minxg/chaos/` | 23 | Lyapunov, attractors, fractals |
| **FIBER** Fiber Bundles | `minxg/fiber/` | 53 | Gauge theory, parallel transport, curvature |

For the full architecture, see **ARCHITECTURE.md**.

---

## 3 · Where to look for what — quick lookup

| You want to… | Look in… |
|--------------|----------|
| Add a new operator | `minxg/operators.py` + the relevant pillar's `operators_*.py` |
| Add a new worker | `minxg/base.py` (use `@tool` decorator) |
| Add a new pillar | Copy `minxg/fiber/` structure, register in `minxg/__init__.py` |
| Change runtime config | `config/minxg.yaml` |
| Change build config | `pyproject.toml` |
| Add a new extension | `extensions/user/<name>/` |
| Add a new translation | `minxg/ai/i18n/catalogs/translations/<locale>.json` |
| Change CLI behavior | `multiligua_cli/main.py` |
| Add an HTTP endpoint | `src/gateway/api/v1/endpoints/` |
| Change logging | `config/minxg.yaml` → `logging.*` |
| Add a new model | `src/ai/models/registry/_registry.py` |
| Tweak self-evolution | `src/ai/memory/behavioral_isomorphism.py` |
| Accelerate hot path | `c_core/libminxg_tidal.so` (Tidal Lock) |
| Translate a doc | Copy `<doc>.md` to `<doc>.zh.md` (or .ja.md / .ko.md) |

---

## 4 · Operator ID allocation (single source of truth)

If you add a new operator, place it in its pillar's range:

| Range | Pillar |
|-------|--------|
| 0 – 19 | math (scalar) |
| 2000 – 2018 | text (string) |
| 3500 – 3511 | data (lists/dicts) |
| 4000 – 4499 | **cat** Category Theory |
| 5000 – 5499 | **ga** Geometric Algebra |
| 5500 – 5512 | logic |
| 6000 – 6499 | **fiber** Fiber Bundles |
| 7000 – 7499 | **infogeo** Information Geometry |
| 8000 – 8499 | **topo** Algebraic Topology |
| 8500 – 8999 | **chaos** Dynamical Systems |
| 9000 – 9005 | system (file/date/env) |
| 10000+ | custom / extension |

This matches `config/minxg.yaml` → `operators.categories`.

---

## 5 · Documentation index

### Root (entry-level)
- [README.md](README.md) — English overview
- [README.zh.md](README.zh.md) — 简体中文
- [README.zh-TW.md](README.zh-TW.md) — 繁體中文
- [README.ja.md](README.ja.md) — 日本語
- [README.ko.md](README.ko.md) — 한국어
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture
- [INSTALL.md](INSTALL.md) — installation
- [QUICKSTART.md](QUICKSTART.md) — 5-minute tour
- [OPERATORS.md](OPERATORS.md) — all 376 operators
- [EXTENSIONS.md](EXTENSIONS.md) — build your own
- [SELF_EVOLUTION.md](SELF_EVOLUTION.md) — the 10 algorithms
- [TIDAL_LOCK.md](TIDAL_LOCK.md) — C acceleration
- [CHANGELOG.md](CHANGELOG.md) — version history

### Per-pillar (in the code directory)
- `minxg/ga/README.md` — Geometric Algebra
- `minxg/cat/README.md` — Category Theory
- `minxg/infogeo/README.md` — Information Geometry
- `minxg/topo/README.md` — Algebraic Topology
- `minxg/chaos/README.md` — Dynamical Systems
- `minxg/fiber/README.md` — Fiber Bundles

(Each pillar's README is also available in `.zh.md`, `.ja.md`, `.ko.md`.)

---

## 6 · Invariants — things that should NEVER change

- The 6 mathematical pillars and their ID ranges (above)
- The fact that `import minxg` is the canonical entry
- `config/minxg.yaml` is the only place to change runtime config
- `py_workers/` is a backward-compat alias — never add new code there
- All `.py` files use 4-space indentation, type hints, no comments
- Every doc has an English canonical version + (zh/ja/ko) if user-facing
