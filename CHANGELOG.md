# CHANGELOG

All notable changes to MINXG are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> **Versioning policy (effective 2026-06-14):** MINXG is in pre-1.0
> development. Public releases start at **`0.10.0`**; the legacy
> `1.x` numbering on internal commits is retained in git history as
> a milestone but is **not** part of the public release graph.

## [0.11.0] - 2026-06-19 - Opt-in extensions, native build fix, doctor command

Cold-start hardening release. No breaking-API changes; all the same
imports work in both directions. The big directional shift: built-in
extensions are now opt-in (no ADB/ROOT auto-detect at module load),
and the `multiligua_cli/doctor.py` self-check surface ships for the
first time.

### Added - `minxg doctor`
  - `multiligua_cli/doctor.py` - new self-check command with an
    exit-code contract (0 OK, 1 fail, 2 warn). Reports on platform,
    binaries, minxg package surface, runtime config, extensions.
  - Plugged into argparse under `minxg doctor` so users have one
    answer for "is my install healthy?".

### Changed - Built-in extensions are opt-in (pitfall 31/34)
  - `extensions/__init__.py` and `extensions/loader.py` rewritten.
    The auto-detect ladder (ADB_AVAILABLE / ROOT_AVAILABLE drive the
    enable flag) is gone. Each built-in now ships with
    `EXTENSION_ENABLED = False`; opt-in is via
    `minxg ext add <slug>`, which writes
    `extensions/user/<slug>.state`.
  - `extensions/builtin/adb_ext/__init__.py`,
    `extensions/builtin/root_ext/__init__.py`,
    `extensions/builtin/files_ext/__init__.py` rewritten in English
    (no Chinese in user-facing strings) with probe-on-call helpers
    (`_adb_available()`, `_root_available()`) instead of
    probe-at-import.
  - `extensions/__init__.py` exports `set_extension_enabled` to back
    the opt-in surface. The `import_hermes_skill` /
    `import_claude_skill` / `import_codex_tool` / `run_ext_import`
    stubs (which referenced an undefined `wrapper_code`) are removed.

### Fixed - cpp_core build link error (real bug)
  - `cpp_core/CMakeLists.txt` built `libminxg_core.so` from
    `cpp_wrapper.c` alone, but the wrapper references
    `minxg_slugify`, `minxg_truncate`, `minxg_word_freq_hash` from
    `c_core/text_engine.c`. The resulting shared library crashed
    every `ctypes.CDLL` call with `cannot locate symbol
    "minxg_slugify"` on Termux/Py3.13.
  - CMakeLists now also links `c_core/text_engine.c` into
    `minxg_core`. Verified at runtime: `core_native.sha256` returns
    correct hashes.
  - `install.sh` no longer claims ADB / ROOT extensions
    "auto-enabled"; users get a plain `minxg ext add <slug>` hint.

### Changed - install.sh
  - Stripped 43 `[CN]` placeholder markers that were left behind from
    an in-progress Chinese-to-English conversion.
  - Removed the auto-enable messaging for ADB / ROOT extensions.
  - Brand line `MINXG v1.0.0` -> `MINXG v0.11.0`.
  - Extension summary block now reports `[on]` / `[off]` based on
    the runtime `enabled` flag, not the old `INACTIVE` substring
    regex.

### Changed - py_workers alias
  - The compat stub now exposes pillar aliases via its own
    `__getattr__`. `py_workers.scalar`, `py_workers.io`,
    `py_workers.<math>` all resolve.
  - Version fallback `getattr(_minxg, 'VERSION', '1.1.0')` ->
    `'0.11.0'`.

### Misc - Housekeeping
  - Bumped `minxg.VERSION` and `pyproject.toml:version` to `0.11.0`.
    `config/minxg.yaml:project.version` synced.
  - Replaced the orphan `multiligua_cli.main:doctor` reference with
    the now-existing `multiligua_cli.doctor.run_doctor`.
  - `multiligua_cli/main.py`: collapsed 19 triple-blank-line blocks
    the partner's draft left behind.
  - `tests/test_extensions.py`: rewrote TestADBRootDetection ->
    TestBuiltinOptIn to assert opt-in (no ADB_AVAILABLE at module
    load, English-only descriptions, state-file persistence works).

### Verification
- 130 tests pass, 1 skipped (rustc absent in Termux sandbox).
- `minxg --version` reports `0.11.0`.
- `bash install.sh --help` exits 0 with the post-install cheatsheet.
- `py_workers.scalar` and `py_workers.ga` resolve via the alias.

## [Unreleased] — Documentation & loader audit

Independent code audit (2026-06-19) found four marketing-vs-reality
gaps and one real loader bug. All five are patched in this entry;
no public version bump (still `0.10.0`).

### Fixed — loader
- **`minxg.five_pillars.scalar.core_native._find_lib()` was searching
  the wrong tree root.** It walked from `minxg/five_pillars/` upward
  only one level, so `cpp_core/build/libminxg_core.so` (the library
  that ships in the repo) was never reached. The Android-Termux
  hardening branch (`shutil.copy2` into
  `/data/data/com.termux/files/usr/lib/`) was therefore dead code on
  the platforms it was written for. The detector now walks up to the
  project root via `pyproject.toml`, checks
  `cpp_core/build/`, `cpp_core/`, and `build/` in that order, and
  still leaves the Android copy-to-lib step intact.
- **Honest fallback message.** Old code's "fall back to
  `minxg_core.so`" returned the bare name when nothing matched,
  leading `ctypes.CDLL` to emit a misleading `dlopen failed` instead
  of a clear "native library not found, run with PURE PYTHON". The
  fallback is now an explicit `OSError` with the actual discovery
  outcome.

### Changed — README / pyproject (marketing accuracy)
- **`pyproject.toml` description.** "376+ math operators" → "306
  mathematical operators (376 total across 11 categories)". `376`
  is real (it's the full `OPERATOR_REGISTRY.total_operators`); `306`
  is the subset exposed as `minxg.TOTAL_MATHEMATICAL_OPERATORS` (the
  sum of the six mathematical pillars). Old wording treated `376`
  as `math`, which is off by 70 and made it sound like 306 of 376
  were missing.
- **`README.md` Mathematical pillars section.** "300+ stable
  operator IDs on import" → "**306** mathematical operator IDs in
  stable ranges on import (376 total across all 11 categories;
  see `OPERATORS.md`)".
- **`README.md` lossless block.** "For lossless compression" →
  "For the lossless BIE round-trip codec" with an explicit caveat
  that the encoded form is typically *larger* than the input on
  real-world data. The bullet under "Self-developed subsystems"
  was rewritten from "BIE-geometry lossless compression" to
  "BIE-geometry byte-identical round-trip" with the same caveat.
  The codec still round-trips byte-exactly (CRC-32 verified); it
  just isn't a competitor to zstd.

### Changed — README (boundary honesty for two subsystems)
- **`minxg.polyglot` description.** "Multi-language AST normaliser"
  → "Multi-language source-to-graph normaliser". Adds explicit
  boundary: Python uses real `ast`; Rust / JavaScript / Go / shell
  are regex-based heuristics — useful for code-shape recognition,
  not a compiler front-end.
- **`README.md` tagline.** "multi-language polyglot, capability
  registry" → no change required (it already names both subsystems
  accurately at the package level). The "corpus" claim in this
  release's subsubsystem remained uncorrected in `minxg.cap` itself;
  cap-tagged source files currently number 7 (3 of which are
  inside `minxg/cap/`). Adoption is voluntary. Reader who wants a
  full corpus can run `python -m minxg.cap list` for the live list.

### Changed — config
- **`config/minxg.yaml` `project.version`.** "0.0.1a" → "0.10.0",
  matching `minxg.VERSION`. `minxg.get("project.version")` now
  returns the same number as `python -c "import minxg; print(minxg.VERSION)"`
  instead of the prior legacy mismatch.
- **`config/minxg.yaml` `project.description`.** Updated to match
  the same one-line summary in `pyproject.toml` and the README.

### Verification
- 130 tests pass + 1 skipped, ~1.5 s on Termux × Python 3.13.
- `python -c "import minxg; print(minxg.VERSION, minxg.TOTAL_MATHEMATICAL_OPERATORS)"`
  → `0.10.0 306`.
- `python -m minxg.cap.list` → 11 capabilities from 7 tagged files.

### Notes
- **`minxg.cap` corpus is small but honest.** README's reference to
  "capability registry" is accurate; the prior "Corpus-based" branding
  survives in CHANGELOG history but was removed from the README-by-
  bullet in this entry. The scanner, manifest, and CI hooks are all
  present and exercised by `tests/test_cap.py`; widening the corpus
  is opt-in (add `minxg.cap.provides:` tags to a module's top
  docstring).

### Further (same Unreleased) — config-truth & ID-range sync
- **`config/minxg.yaml` `self_evolution.algorithms: 10` → `components: 4`.**
  The repository ships exactly four cooperating pieces
  (`failure_tour.py`, `field_forge.py`, `twin.py`, `loop.py`). The
  old `algorithms: 10` was a marketing number with no backing code.
- **`config/minxg.yaml` `features.{hot_reload, anti_loop_guard,
  tidal_lock}` flipped to `false`.** README and CHANGELOG history
  have described each as removed / unimplemented since v1.1.x, but
  the YAML was advertising them as `true`. Truthful defaults now match
  the documented reality.
- **`config/minxg.yaml` dropped `self_evolution.compression: zstd-level-3`.**
  No code path under `minxg/self_evolution/` reads this value.
- **Pillar ID ranges in README + DEVELOPER.md corrected** from the
  outdated `5000–5499` / `4000–4499` / etc. (which reserved ~100 IDs
  per pillar that were never registered) to the actual ranges
  observed in `OPERATOR_REGISTRY._categories` — see YAML
  `operators.categories.*.id_range` for the canonical numbers.
- **Top-level README tagline softened** from "covering the full
  operator surface area" to a non-promissory phrasing. Also added a
  paragraph explaining the implicit pure-Python fallback when the
  native loader cannot find or dlopen a `.so`.
- **DEVELOPER.md §11 "Termux linker namespace" entry now lists the
  exact discovery order** (`cpp_core/build/` → `cpp_core/` → `build/`)
  and the explicit-OSError contract, so the next maintainer doesn't
  waste a session re-discovering what `core_native._find_lib` does.


This release supersedes both the original 0.10.0 snapshot and the
0.11.0 hot-fix re-versioning. Source-of-truth tag is **v0.10.0**.

### Fixed
- **Cold-start cryptography crash.** `multiling/ipc_server.py` no
  longer imports `cryptography` at module level. The dependency is
  lazy-loaded inside `_generate_ssl_cert()` and only when TLS is
  requested. Fixes `minxg tools` and `minxg open` failing on
  Termux × Python 3.13 (`cannot locate symbol "PyBaseObject_Type"`).
- **`ChatLogger._buffer` initialised in `__init__`.** `minxg files`,
  `minxg adb`, `minxg root`, and the TUI default (`minxg` with no
  args) used to flake with `AttributeError: '_buffer'` on first use.
- **`MinxgMenu.run()` non-readchar branch.** Clean fallback to
  numbered input with a `q`-to-quit exit when `readchar` is not
  available — no broken `NameError: choice` mid-flow.
- **Hardcoded version literals.** `multiligua_cli/utils.py`,
  `setup.py`, and `wizard_ui.py` no longer leak `"1.0.0"` while
  `minxg.VERSION` is on a different number. All consumer-facing
  labels now read `minxg.VERSION` via guarded import.
- **`multiligua_cli/i18n.py` fallback.** A built-in `_DEFAULTS`
  English dictionary ships inside the module, so a missing
  `i18n_data/en.json` no longer surfaces raw keys (e.g. `cmd_minxg`)
  in `minxg help` and the cheatsheet.
- **`multiligua_cli/providers.py` registry.** 32 AI providers
  (qwen, zhipu, moonshot, baichuan, stepfun, doubao, yi, spark,
  minimax, custom, local, …) all carry `name`, `emoji`, and
  `description` keys. The setup wizard no longer crashes with
  `KeyError: 'emoji'` when picking an AI provider.
- **`multiligua_cli/extensions/tui.py quick_list()`** constructs
  its Rich `Table` before iterating — previously referenced an
  unbound `table` name and crashed on every `minxg ext list`.

### Build / install hygiene
- Removed legacy editable-install leftovers from
  `/data/data/com.termux/files/usr/lib/python3.13/site-packages`
  (`__editable__.minxg-0.0.1a0.pth`, `multiling-3.4.0.dist-info`,
  `__editable___minxg_0_0_1a0_finder.py`, …) that were shadowing
  the live install and pointing at a stale `/storage/emulated/0/multiling/`
  working tree. Reinstall is clean via `pip install -e .`.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [0.11.0] — Re-versioning hot-fix (+0.01)  *[superseded by 0.10.0 above]*

### Changed
- **Re-versioned** `0.10.0` → `0.11.0`. No code changes; this is a
  marker commit to increment the public number on top of the
  original 0.10.0 snapshot, per project policy.
- `minxg.VERSION`, `pyproject.toml`, README all reflect `0.11.0`.
- CHANGELOG prepended with this entry; `0.10.0` section retained
  below as the source-of-truth snapshot for that tag.
- **Note:** The v0.11.0 GitHub release was deleted as part of the
  v0.10.0 re-release; the underlying commit history is preserved.

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
