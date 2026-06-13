# MINXG-Beta — User Guide

> Five-minute tour. If you've never used MINXG-Beta, start here.

## What is it?

MINXG-Beta is a pure-Python framework that turns **376 typed operators** —
drawn from six mathematical pillars (geometry, category theory,
information geometry, topology, dynamical systems, fiber bundles) — into
tools any agent or CLI can call. You get the algebra; the framework
handles registration, dispatch, type-checked composition, native
acceleration, and self-evolution.

It runs on Termux, Linux, macOS, and any Linux server with Python 3.11+.

## Install

One command (does everything: venv, pip install editable, sanity check):

```bash
/bin/bash <(curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh)
```

Or classical:

```bash
git clone https://github.com/Disability-Human/MINXG-Beta.git
cd MINXG-Beta
pip install -e ".[dev]"
minxg --version        # smoke test
```

## First 60 seconds

```python
import minxg
from minxg.operators import OPERATOR_REGISTRY

# How big is the operator catalog?
print(OPERATOR_REGISTRY.total_operators)        # 376

# Look one up by ID — IDs are opaque, deterministic, and stable across versions
op = OPERATOR_REGISTRY.get_by_id(5001)         # GA geometric product
print(op.name, op.category)

# Call it
result = op.fn([1, 2, 3], [4, 5, 6])
```

## What's in the box (one line per pillar)

| Pillar | What it lets you compute |
|--------|--------------------------|
| `ga`     | Multivector products, rotors, reflections, translations, dilations |
| `cat`    | Monadic computations (`Maybe`, `Either`, `State`, `Reader`, `IO`), Yoneda embedding |
| `infogeo`| Fisher information, natural gradient, KL/JS/Rényi/Bregman divergences |
| `topo`   | Persistent homology, Betti numbers, Vietoris-Rips, Wasserstein distances |
| `chaos`  | Logistic / Lorenz / Rössler / Duffing maps, Lyapunov spectra, fractals |
| `fiber`  | Covariant derivatives, parallel transport, Riemann curvature, geodesics |

See **[OPERATORS.md](../archive/OPERATORS.md)** for the full catalog
or `docs/developers/` to learn how to register your own.

## CLI

```bash
minxg --version               # show version
minxg list ops                # list all registered operators
minxg list ops --category ga  # filter by pillar
minxg call 5001 "[1,2,3]" "[4,5,6]"
minxg serve                   # start the OpenAI-compatible gateway
```

## Native speedups (optional)

Pure Python is always sufficient — native modules are pure
acceleration. To compile and use C/C++/Go backends:

```bash
bash scripts/build_native.sh   # compiles c_core, cpp_core, go_core
python -c "import minxg; print(minxg.core_native.ready())"
```

If the build fails (or you're on a hostile platform), nothing breaks —
the runtime silently falls back to pure Python.

## Where to go next

- Want to **use** the framework: skim this file once, you're done.
- Want to **extend** it: go to `docs/developers/extending.md`.
- Want to **understand** it: start with `docs/developers/architecture.md`.
- Lost? `python -c "help(minxg)"` lists every public symbol.

## License

MIT. See [LICENSE](../../LICENSE).
