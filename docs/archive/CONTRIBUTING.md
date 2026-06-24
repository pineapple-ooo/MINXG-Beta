# Contributing to MINXG

MINXG is a mathematical operator framework — contributions that add rigor,
generality, or elegance are warmly welcomed.

## Rules of the codebase

1. **Pure Python by default.** All 6 mathematical pillars run without numpy,
   scipy, or any compiled dependency. Keep it that way.
2. **One public API per concept.** Each operator exports exactly one way
   to do a thing. If there are two ways, one is wrong.
3. **Tests before merge.** Every new operator or changed behavior needs
   a test in `tests/`.
4. **Examples as documentation.** The examples in `examples/` double as
   integration tests. If you add a major feature, add an example.
5. **No comments in math code.** The algebra speaks for itself. Comments
   are for *why*, not *what* — and only when the *why* is non-obvious.
6. **No dead code.** If it's not tested, it doesn't exist. Empty
   directories and placeholder files are banned.

## Setup

```bash
git clone https://github.com/minxg/minxg.git
cd minxg
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

All 66 tests should pass. The suite covers every mathematical pillar +
operator registry + config.

## Project structure

```
minxg/          # The mathematical core (376 operators, 6 pillars)
  ga/           # Geometric Algebra
  cat/          # Category Theory
  infogeo/      # Information Geometry
  topo/         # Algebraic Topology
  chaos/        # Dynamical Systems & Chaos
  fiber/        # Fiber Bundles
tests/          # pytest regression suite
examples/       # Runnable demos (also integration tests)
c_core/         # C acceleration (Tidal Lock)
config/         # minxg.yaml — source of truth
```

## Adding a new operator

1. Pick the right pillar (or create a new one — see EXTENSIONS.md).
2. Register in `minxg/<pillar>/operators_<pillar>.py` with a unique ID
   in the pillar's ID range (see PROJECT_INDEX.md §4).
3. Write a test in `tests/`.
4. Update `config/minxg.yaml` operator count.
5. Run the full test suite.

## Commit style

- `ga: fix rotor inverse norm` — pillar-scoped
- `tests: add config regression tests`
- `docs: update quickstart for chaos pillar`

## Questions?

Open an issue or read the architecture: [ARCHITECTURE.md](ARCHITECTURE.md)