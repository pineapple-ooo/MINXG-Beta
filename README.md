# MINXG

A modular AI worker platform organised as five orthogonal operator
planes, plus a self-developed driver engine, plus six categorical
operator libraries, plus optional languages / compression / twin
compilers / docs lenses.

One small pip install. Pure Python. Runs on Termux.

## Install

```
pip install minxg-beta
```

Optional native acceleration (speeds up crypto + IO workers):

```
pip install "minxg-beta[fast]"
```

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

For lossless compression:

```python
from minxg.lossless import LosslessCodec

codec = LosslessCodec()
blob = codec.compress(b"some payload") .payload
back  = codec.decompress(blob)
assert back == b"some payload"
```

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
* `minxg.polyglot` — Multi-language AST normaliser. Python / Rust /
  JavaScript / Go / shell all reduce to a single `OperatorGraph`.
* `minxg.lossless` — BIE-geometry lossless compression. Every byte
  becomes a unit-sphere point; transitions between bytes become
  blades; the curvature skeleton is what gets stored, with a CRC-32
  for byte-identical reconstruction.
* `minxg.twin` — Python ↔ Rust RTL compiler. Source-equivalent twin
  emitters cover if/elif/else, while/for-range, augmented assignments,
  binop/compare expressions.
* `minxg.lens` — Reverse-docstring exporter. Render any one
  description into EN / ZH / ZH-TW / JA / KO doc files + a glossary.

## Mathematical pillars

Six categorical libraries ship with the package and register
300+ stable operator IDs on import:

```
minxg.ga         5000-5499   geometric algebra
minxg.cat        4000-4499   category theory
minxg.infogeo    7000-7499   information geometry
minxg.topo       8000-8499   algebraic topology
minxg.chaos      8500-8999   dynamical systems
minxg.fiber      6000-6499   fiber bundles
```

## Documentation

* `DEVELOPER.md` — full developer reference, one file
* `docs/ARCHITECTURE.md` — architecture diagrams and rationale
* `docs/DRIVER.md` — driver engine API and examples
* `docs/PILLARS.md` — one section per mathematical pillar

## License

MIT. See `LICENSE`.
