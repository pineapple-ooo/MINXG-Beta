# MINXG

A modular AI worker platform with a built-in chat CLI, an OpenAI-compatible
v1 gateway, opt-in extensions (ADB / ROOT / files), and a self-developed
temporal driver engine — all in one Python package.

`pip install minxg-beta` drops you on Termux, Linux, macOS, and WSL
with a single `minxg` binary on `$PATH`. Workers are split across
five orthogonal operator planes (io, aggregate, scalar, transform,
dispatch), so editing one module never forces a full rebuild.
Pure Python — no compiled step required to install or run.

This is the **v0.11.0** release. It ships cold-start hardening plus
a polished setup wizard:

- `minxg` (no subcommand) now asks: chat CLI, start API gateway, or
  run the setup wizard — instead of dropping straight into a TUI
  shell.
- Setup wizard supports the OpenAI-standard `reasoning_effort` knob
  (`xhigh` / `high` / `medium` / `low` / `minimal` / `none`) with
  per-provider support maps (OpenAI supports all five, Anthropic
  three, Gemini five, DeepSeek / Doubao / xAI four, etc.).
- Wizard menus strictly fit a single line per option — descriptions
  are truncated to 28 chars so Termux 80-col screens stop spilling
  one option across two terminal rows.
- Built-in extensions (`minxg-adb`, `minxg-root`, `minxg-files`)
  ship opted-OUT. Users enable with `minxg ext add <slug>`. No
  silent auto-attaching to whatever API happens to be on PATH.
- `cpp_core/CMakeLists.txt` link error fixed: `libminxg_core.so`
  no longer crashes on `dlopen` with
  `cannot locate symbol "minxg_slugify"` on Termux + Py3.13.
- `minxg model`: the AI provider registry was missing `name`,
  `emoji`, and `description` for the second half of the providers,
  crashing the setup wizard with `KeyError: 'emoji'`. All 32
  providers are now normalised.
- `cpp_core/src/json_stringify.cpp` adds a flat C ABI over the C++
  `json_fast` parser (re-parses per call so no `std::variant`
  crosses the boundary on aarch64 Android, returns malloc'd buffers
  freed via `cpp_json_free`). Exposed to Python through
  `native_integration.CPPJsonNative` with a `JsonBuffer` lifetime
  wrapper that holds the raw `c_void_p` pointer (the heap-corruption
  footgun from using `c_char_p` is now memoralised at the top of the
  class).
- `java_core/` ships a polyglot JVM-side daemon — line-oriented JSON
  RPC on TCP, in-memory vector engine, knowledge graph, session
  memory, persistent log — built with `javac` (no Maven/Gradle
  required). Intended for users who already run a JVM and want a
  hostable backend independent of the Python driver. Source-only;
  build artefacts (`build/`, `*.jar`) stay out of git via the
  existing `.gitignore`.

## Install

The Python package's distribution name is **`minxg-beta`** and the
top-level import is **`minxg`**.

### One-liner (any platform)

```bash
curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash
```

That single command:
- detects your platform (Termux / Linux / macOS / WSL),
- clones the full repo to `~/.minxg-src`,
- pip-installs everything in editable mode so the `minxg` console
  script lands on `$PATH`,
- compiles the optional C extensions if a compiler is present,
- prints a status table at the end.

Variants:

```bash
# custom clone dir
MINXG_DIR=/opt/minxg curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash

# explicit repo URL (when forking)
REPO_URL=https://github.com/you/minxg.git curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash
```

### Local clone (developer)

```bash
git clone https://github.com/<owner>/minxg.git
cd minxg
bash install.sh          # picks up the existing clone, skips the git step

After install:

```python
import minxg
print(minxg.VERSION)         # "0.10.0"
print(minxg.detect_platform())
```

Verified end-to-end on Termux/Android (`Python 3.13`) and Linux:
```bash
$ pip install -e .
Successfully installed minxg-beta-0.10.0

$ python3 -c "import minxg; print(minxg.VERSION, len(minxg.__all__), 'workers;', minxg.TOTAL_MATHEMATICAL_OPERATORS, 'math ops')"
0.10.0 55 workers; 306 math ops
```

**PyPI publication is on the roadmap but not yet done.** Until the
package shows up on PyPI under the `minxg-beta` name, the source-
tree mode above is the supported install path.

The codebase has no compiled dependencies on install; everything in
`minxg/five_pillars/`, `minxg/driver/`, `minxg/contracts/`,
`minxg/self_evolution/`, `minxg/polyglot/`, `minxg/lossless/`,
`minxg/twin/`, `minxg/lens/`, and the six mathematical pillars is
pure Python. Fall-back to pure Python is implicit: when no native
library is found or `dlopen` fails, the Python implementation is
used. The Termux/Android pipeline runs end-to-end via the lazy
loader for `cryptography` and the project-root-anchored
`core_native._find_lib` walker.

## Quick start

```python
import minxg

print(minxg.VERSION)
print(minxg.detect_platform())

fs = minxg.FsIoWorker()
result = await fs.list_directory(path="/tmp")
```

For the driver engine (substitute for a task graph):

```python
from minxg.driver import State, DriverEngine, smoothing_field

state = State(payload={"x": 0.0, "v": 1.0})
engine = DriverEngine([smoothing_field(rate=0.4)])
end, report = engine.run(state, n_steps=24)
```

For the lossless BIE round-trip codec:

```python
from minxg.lossless import LosslessCodec

codec = LosslessCodec()
result = codec.compress(b"some payload")     # wraps an MINSKE blob + CRC-32
back = codec.decompress(result.payload)
assert back == b"some payload"               # byte-identical, not size-optimised
```

This is a BIE (blade-decomposition) *byte-identical round-trip* — useful
as a structured representation of byte streams, not a competitor to
zstd/gzip. On random or low-redundancy inputs the encoded form is
larger than the source.

## Five pillars

The 55 worker classes are organised along five orthogonal planes:

```
minxg.five_pillars.scalar       pure compute        math / datetime / text / color
minxg.five_pillars.aggregate    encoders            crypto / encoding / ml / templates
minxg.five_pillars.io           external surfaces   fs / net / media / web / cloud
minxg.five_pillars.dispatch     execution / limits  system / sh / adb / root
minxg.five_pillars.transform    state and events    persistence / rules / ai
```

Edit one worker, nothing else moves.

## Self-developed subsystems

* `minxg.driver` — Temporal Operator-Field driver engine. Operators
  are pure functions on a shared state manifold; advancing one step
  is explicit Euler integration with adaptive sub-stepping on drift.
* `minxg.contracts` — Operator-Cell registry. Each Cell advertises
  capabilities; replacing one Cell never touches the others.
* `minxg.self_evolution` — Closed-loop self-improvement. A bouncer
  records engine failures, a forge hunts capable Cells from the
  contracts registry, a twin engine validates a swap is drift-safe
  before committing.
* `minxg.polyglot` — Multi-language source-to-graph normaliser.
  Python uses real `ast`; Rust / JavaScript / Go / shell use
  regex-based structural heuristics (not full parsers). All five
  reduce to a single `OperatorGraph` with topological-order
  edges — good enough for code-shape recognition, not a compiler
  front-end.
* `minxg.lossless` — BIE-geometry byte-identical round-trip. Every
  byte becomes a unit-sphere point; transitions between bytes
  become blades; the curvature skeleton is what gets stored, with
  a CRC-32 trailer guaranteeing byte-identical reconstruction.
  Structurally interesting; output is typically *larger* than the
  input on real-world data.
* `minxg.twin` — Python ↔ Rust RTL compiler. Source-equivalent twin
  emitters cover if/elif/else, while/for-range, augmented assignments,
  binop/compare expressions.
* `minxg.lens` — Reverse-docstring exporter. Render any one
  description into EN / ZH / ZH-TW / JA / KO doc files + a glossary.

## Mathematical pillars

Six categorical libraries ship with the package and register
**306 mathematical operator IDs** in 6 non-overlapping ranges on
import (376 operators total across all 11 categories; see
`OPERATORS.md`):

```
minxg.ga         5000-5049   geometric algebra       (47 ids)
minxg.cat        4000-4078   category theory         (79 ids)
minxg.infogeo    7000-7050   information geometry    (51 ids)
minxg.topo       8000-8052   algebraic topology      (53 ids)
minxg.chaos      8500-8522   dynamical systems       (23 ids)
minxg.fiber      6000-6052   fiber bundles           (53 ids)
```

## Documentation

* `DEVELOPER.md` — full developer reference, one file
* `docs/ARCHITECTURE.md` — architecture diagrams and rationale
* `docs/DRIVER.md` — driver engine API and examples
* `docs/PILLARS.md` — one section per mathematical pillar

## License

MIT. See `LICENSE`.
