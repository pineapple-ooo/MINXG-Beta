# MINXG

A modular AI worker platform with a self-developed driver engine and six
mathematical operator pillars, written in pure Python and engineered to
run anywhere Termux runs.

## What is it

MINXG is one Python package split into five functional pillars plus an
independent driver engine plus six mathematical-pillar operator libraries.
Add or replace a single module without touching the rest of the project.

## Install

```
pip install minxg
```

Termux / Android / Linux / macOS — pure Python, no compiled dependency
required at install time. Optional native modules are detected at runtime.

## Quick start

```python
import minxg

print(minxg.VERSION)
print(minxg.detect_platform())

fs = minxg.FsIoWorker()
files = minxg.run_async(fs.list_directory(path="/tmp"))
```

## Five Pillars

The 50+ worker classes are organised along five orthogonal planes so that
no two classes share an import path:

```
minxg.five_pillars.scalar       pure compute (math, datetime, text, color)
minxg.five_pillars.aggregate    encoders and aggregators (crypto, encoding, ml)
minxg.five_pillars.io           external surfaces (fs, network, media, web)
minxg.five_pillars.dispatch     execution and limits (system, sh, adb, root)
minxg.five_pillars.transform    state and persistence (events, rules, hot-reload)
```

Edit one worker, nothing else moves.

## Driver engine

`minxg.driver` treats each operator as a vector field on a shared state
manifold and advances the state through explicit Euler integration with
adaptive sub-stepping. See `docs/DRIVER.md` for the math.

```python
from minxg.driver import State, DriverEngine, arithmetic_field, smoothing_field

state = State(payload={"x": 0.0})
engine = DriverEngine([
    arithmetic_field(lambda s: {"x": 1.0}),
    smoothing_field(rate=0.4),
])
result, report = engine.step(state)
```

## Mathematical pillars

Six additional sub-packages provide operator libraries grounded in
mathematical structures: `minxg.ga`, `minxg.cat`, `minxg.infogeo`,
`minxg.topo`, `minxg.chaos`, `minxg.fiber`. They auto-register on import
and contribute 300+ operators.

## Contracts

`minxg.contracts` is the pluggable Cell-Registry pattern: every worker
advertises capabilities, registers through one shared registry, and never
imports another worker directly. Replacing a worker changes only the
registry entry.

## Documentation

* `DEVELOPER.md` — full developer reference, one file
* `docs/ARCHITECTURE.md` — architecture diagrams and rationale
* `docs/DRIVER.md` — driver engine API and examples
* `docs/PILLARS.md` — one section per mathematical pillar

## License

MIT.
