# CHANGELOG

All notable changes to MINXG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> **Versioning policy (effective 2026-06-14):** MINXG is in pre-1.0
> development. Public releases start at **`0.10.0`**; the legacy
> `1.x` numbering on internal commits is retained in git history as
> a milestone but is **not** part of the public release graph.

## [0.11.0] — Re-versioning hot-fix (+0.01)

### Changed
- **Re-versioned** `0.10.0` → `0.11.0`. No code changes; this is a
  marker commit to increment the public number on top of the
  original 0.10.0 snapshot, per project policy.
- `minxg.VERSION`, `pyproject.toml`, README all reflect `0.11.0`.
- CHANGELOG prepended with this entry; `0.10.0` section retained
  below as the source-of-truth snapshot for that tag.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [0.10.0] — Corpus-based Capability Registry (first 0.x public release)

### Added
- `minxg.cap` — Corpus-based Capability Registry. Scans every Cell's
  `Capability` declarations across the contracts registry and exposes
  a single, queryable index (`cap lookup`, `cap info`, `cap diff`,
  `cap tree`, `cap regen`, `cap ci`). Backed by a deterministic
  manifest (`manifest.json`) keyed by Cell identity + capability
  signature, so two warehouse clones can be diff-ed byte-stable.
  Runs as a CLI (`python -m minxg.cap`) and as a normative gate in
  CI (`tests/test_cap.py`).
- First-time release-automation path: `git tag -a v0.10.0` →
  `gh release create v0.10.0 --target main`.

### Changed
- **Re-versioned:** `minxg.VERSION`, `pyproject.toml`, README are
  now `0.10.0`. Changelog history above `0.10.0` is preserved under
  the legacy section for trace-ability of internal milestones
  (v0.0.1a → v0.0.2-audit → v1.1.0 → v1.2.0 → v1.3.0-internal).
- `minxg/__init__.py` re-exports the `cap` submodule under a
  guarded import so `import minxg.cap` keeps working.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [1.3.0-internal] — Corpus-based Capability Registry (legacy numbering)

> Internal milestone — superseded by **0.10.0** as the first public
> release on 2026-06-14. The commit graph is preserved; the public
> tag was removed (only the GitHub-protected `v1.3.0` tag object
> remains in history as a reference point). Do **not** depend on this
> version externally.

### Added
- `minxg.cap` — Corpus-based Capability Registry. Scans every Cell's
  `Capability` declarations across the contracts registry and exposes
  a single, queryable index (`cap lookup`, `cap info`, `cap diff`,
  `cap tree`, `cap regen`, `cap ci`). Backed by a deterministic
  manifest (`manifest.json`) keyed by Cell identity + capability
  signature, so two warehouse clones can be diff-ed byte-stable.
  Runs as a CLI (`python -m minxg.cap`) and as a normative gate in
  CI (`tests/test_cap.py`).
- Tests for the cap subsystem: 16 tests, all passing.

### Changed
- `minxg.VERSION` is now `"1.3.0"`.
- `pyproject.toml` `version = "1.3.0"`.
- `minxg/__init__.py` now re-exports the `cap` submodule under a
  guarded import so `import minxg.cap` continues to work.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [1.2.0] — Self-developed subsystems

### Added
- `minxg.contracts` — Cell / Port / Registry / Lifecycle framework.
  Cells advertise capabilities through a `CellMeta` metaclass and are
  registered once into a `Registry` that other Cells consult by
  capability name. Editing one Cell never touches the others.
- `minxg.driver` — Temporal Operator-Field driver engine. Operators
  are pure `State → State` mappings; the engine advances time with
  explicit Euler integration and adaptive sub-stepping on drift.
  Five phases (`ready`, `stepping`, `paused`, `halted`, `faulted`)
  exposed through `engine.on_phase(prev, new)` hooks.
- `minxg.self_evolution` — closed-loop self-improvement. `FailureTour`
  records engine failures; `FieldForge` queries the contracts
  registry for capable Cells; `TwinEngine` validates a swap on a
  shadow copy of the live engine; `EvolutionLoop.cycle()` commits
  the swap on twin-accept.
- `minxg.polyglot` — multi-language AST normaliser. Reduces Python /
  Rust / JavaScript / Go / shell to a single `OperatorGraph` shape
  with topological-order support. Pure Python; Rust/JS/Go/shell
  use regex heuristics.
- `minxg.lossless` — BIE-geometry lossless compression. Each byte
  becomes a unit-sphere point; byte-to-byte transitions become
  blades; the curvature skeleton is what gets stored, with a
  CRC-32 trailer guaranteeing byte-identical reconstruction.
- `minxg.twin` — Python ↔ Rust RTL emitter. `python_to_rust` covers
  function definitions, if / elif / else, while, for-range,
  augmented assignments, all standard expressions. `rust_to_python`
  reverses. Unsupported constructs raise `UnsupportedTwinOp`.
- `minxg.lens` — reverse docstring export. Bundled 14-entry
  glossary (operator / driver / bridge / registry / cell / port /
  field / state / drift / blade / curvature / worker / twin /
  evolution) maps EN → ZH / ZH-TW / JA / KO. Lens renders every
  section in every language, with a `GLOSSARY.md` summary table.

### Changed
- `minxg.VERSION` is now `"1.2.0"`.
- `pyproject.toml` `version = "1.2.0"`, license author "MINXG Authors".
- New top-level constants exported from `minxg.__init__`:
  `POLYGLOT_LANGUAGES`, `LOSSLESS_MAGIC`, `LOSSLESS_VERSION`,
  `TWIN_ERROR`, `SELF_EVOLUTION_PHASES`, `LENS_LANGUAGES`,
  `DRIVER_PHASES`, `DRIVER_DEFAULT_MAX_SUBDIVISIONS`.

### Tests
- 114 passed (+1 skipped, no rustc on Termux), ~2 s

## [1.1.0] — Five-pillar layout + contracts + driver + hot-reload removed

### Added
- `minxg/five_pillars/{scalar, aggregate, io, dispatch, transform}`
  layout — flat worker files moved into five orthogonal planes.
  Each pillar only depends on `minxg.base`; cross-pillar imports are
  fully qualified.
- `minxg/five_pillars/` re-exports the public surface so
  `from minxg import FsIoWorker` still works.

### Removed
- GitHub hot-reload subsystem. `multiligua_cli/hot_reload.py`,
  the `update` subcommand, the `/update` TUI shortcut,
  `setup_hot_reload`'s repo/branch prompts are gone. Use
  `pip install --upgrade minxg-beta` instead. See
  `docs/ARCHITECTURE.md` § "Self-evolution loop" for the rationale.

### Changed
- `minxg.driver` previously existed as the engine scaffold;
  promoted to a fully-implemented subsystem in v1.2.0.
- `py_workers/` is now a thin alias package with `__getattr__`
  pointing flat module names at `minxg.five_pillars.<p>.<x>`.

## [0.0.2-audit] — Repo hygiene & CI hardening

### Added

- `LICENSE` at repo root (MIT, matches `pyproject.toml`)
- `.env.example` template (real `.env` is git-ignored and chmod-locked)
- `.github/workflows/ci.yml` now asserts `OPERATOR_REGISTRY.total_operators == 376` and runs a separate `ruff` job
- `OPERATORS.md`: "How we count" — exact count is CI-enforced, not hand-edited
- `OPERATORS.md`: "Why these six pillars" — diff against functional taxonomy
- `ARCHITECTURE.md` § 5 rewritten with `c_core/` ↔ `cpp_core/` ↔ `go_core/` boundary policy and Termux/CDLLCID idiom
- `_legacy/README.md` — explains the legacy vault, sets a review cadence

### Fixed

- 43 source files still declared `py_workers/...` in their docstring banners after the rename → renamed to `minxg/...` (compat alias preserved)
- `minxg/ga/operators_ga.py` ID-range comment said `3500-4499`; actually registers at `5000-5049` → comment now matches
- README badge linking to `opensource.org/licenses/MIT` (generic) → linked to repo's own `LICENSE`
- `.gitignore` extended to suppress `_legacy/` and `.test_entropic/` from GitHub browsing

### Hygiene

- Removed stale `minxg.egg-info/` and `multiling.egg-info/`
- Real `.env` chmod-locked (`444`) to prevent accidental overwrite

## [0.0.2] — Architecture overhaul & documentation upgrade

### Changed — package renamed

- `py_workers/` renamed to **`minxg/`** (single canonical import)
- `py_workers/` retained as a backward-compat alias
- `pyproject.toml` `name = "minxg"`
- All cross-package imports updated
- No breaking change for users: `import py_workers` still works

### Added — centralized configuration

- `config/minxg.yaml` is the single source of truth for runtime config
  (project metadata, operator counts, pillar definitions, paths, features)
- `minxg.get(key)` reads config via dot-path (e.g. `minxg.get("project.version")`)

### Changed — documentation reorganization

- `docs/` directory **removed** (was redundant with project root)
- All HTML files **removed** (we use Markdown only)
- New root-level documents (each available in 5 languages where applicable):
  - `PROJECT_INDEX.md` — one-page project map
  - `ARCHITECTURE.md` — full system architecture
  - `INSTALL.md` — installation everywhere
  - `QUICKSTART.md` — 5-minute tour
  - `OPERATORS.md` — all 376 operators
  - `EXTENSIONS.md` — build your own
  - `SELF_EVOLUTION.md` — the 10 algorithms
  - `TIDAL_LOCK.md` — C acceleration
- All pillar READMEs (`.md`, `.zh.md`, `.ja.md`, `.ko.md`) live **next to
  the code** (in `minxg/<pillar>/`) — finding pillar docs no longer
  requires searching the whole repo
- All `5 root-level READMEs` (en / zh / zh-TW / ja / ko)

### Changed — comment hygiene

- All inline comments and decorative docstrings removed from
  `minxg/` Python files (the code reads itself)
- Public API docstrings retained

### Fixed

- Cloud tools `env_template` f-string regression caused by overzealous
  comment stripping — fixed

## [0.0.1a] — Initial alpha with 6 mathematical pillars

### Added

- 6 mathematical pillars (306 new operators) on top of original 70:
  - **GA** Geometric Algebra (Clifford) — 47 operators
  - **CAT** Category Theory — 79 operators
  - **IG** Information Geometry — 51 operators
  - **TOPO** Algebraic Topology — 53 operators
  - **CHAOS** Dynamical Systems & Chaos — 23 operators
  - **FIBER** Fiber Bundles — 53 operators
- Pure-Python implementations (no numpy)
- Original 10 self-evolution algorithms
- Tidal Lock C acceleration (11 functions)
- 50+ workers (FS, network, state, crypto, ML, system, process)
- Multi-platform support (Termux, Linux, macOS, iOS, IoT)

### Total: 376 operators, 11 categories, 6 mathematical pillars
