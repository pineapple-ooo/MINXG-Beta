# CHANGELOG

All notable changes to MINXG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
