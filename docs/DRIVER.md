# MINXG Driver Engine

The driver engine treats each operation as a vector field on a shared
state manifold and integrates the state through explicit Euler steps.

## When to use the driver

Reach for the driver when your task looks like a sequence of related
transformations on a shared numeric state, especially when:

* you want order-independence (commuting operations never break each
  other)
* you want to add/remove a transformation without rewriting tests
* the system has drift sensitivities (chaotic, stiff, multimodal)

For one-shot dispatch use `minxg.base` workers directly.

## Building an engine

```python
from minxg.driver import (
    State, DriverEngine, arithmetic_field,
    parametric_field, smoothing_field, clamp_field,
)

state = State(
    payload={"x": 0.0, "v": 1.0},
    bounds={"x": (-10.0, 10.0)},
)

engine = DriverEngine(
    [
        arithmetic_field(lambda s: {"v": 0.1}, name="acceleration"),
        clamp_field(-1.0, 1.0),
        smoothing_field(rate=0.2),
    ],
    step_size=0.5,
    max_drift=1.0,
    max_subdivisions=4,
)

new_state, report = engine.step(state)
```

`StepReport` returns:

* `step`: monotonic step counter
* `timestamp`: post-step time
* `drift`: Euclidean distance between start and end states
* `subdivisions`: how many times the engine halved `dt` to keep drift in
  bounds
* `operator_count`: number of operators in this engine
* `notes`: human-readable phase observations

## Adaptive sub-stepping

Each step computes drift. If drift exceeds `max_drift`, the engine
halves `dt` and retries, up to `max_subdivisions` times. This means
chaotic fields stay stable even with a large nominal `step_size`.

## Hooking phase changes

```python
from minxg.driver import EnginePhase

engine.on_phase(lambda prev, new: log.info("%s → %s", prev, new))
```

Phases:

* `READY`    – accepting work
* `STEPPING` – mid-step
* `PAUSED`   – user-requested pause; `step()` is a no-op
* `HALTED`   – stop until `reset()`
* `FAULTED`  – unrecoverable error; `reset()` then resume

## Removing and replacing operators

```python
engine.remove_operator("acceleration")
engine.replace_operator(0, parametric_field("new_a", 0.05, "x"))
```

No state is invalidated, no other engine is affected. The registry hot
swap is the leverage that lets you repurpose a running engine for A/B
testing without restarting.

## Custom operators

```python
from minxg.driver import Operator
from minxg.driver.state import State

class DriftToward(Operator):
    name = "drift_toward"

    def __init__(self, target: dict, rate: float = 0.1):
        self.target = target
        self.rate = rate

    def apply(self, state: State) -> State:
        out = state.clone()
        for k, v in self.target.items():
            current = out.payload.get(k, 0.0)
            out.payload[k] = current + (v - current) * self.rate
        return out

engine.add_operator(DriftToward({"x": 5.0}, rate=0.25))
```

## Combination with workers

Operators are pure-Python, no I/O. To mix a worker into a driver, wrap
its async method:

```python
import asyncio
from minxg.driver import Operator, State

class WorkerOperator(Operator):
    name = "fsworker.read"

    def __init__(self, instance, method: str):
        self.instance = instance
        self.method = method

    def apply(self, state: State) -> State:
        out = state.clone()
        method = getattr(self.instance, self.method)
        result = asyncio.run(method(**out.payload))
        out.payload["last_result"] = hash(tuple(sorted(result.items())))
        return out
```

This is the bridge between the worker system and the driver — and it
inherits the operator's pure semantics, so swapping a worker still
doesn't break other operators.

## API summary

| Symbol            | Where            | Notes                          |
|-------------------|------------------|--------------------------------|
| `State`           | state.py         | Numerical payload + bounds     |
| `Operator`        | operator.py      | Base class for fields          |
| `Identity`        | operator.py      | `f(x) = x`                     |
| `Composition`     | operator.py      | `left ∘ right`                 |
| `DriverEngine`    | engine.py        | Integration loop               |
| `StepReport`      | engine.py        | Per-step diagnostic            |
| `EnginePhase`     | engine.py        | Phase enum                     |
| `Field`           | fields.py        | Operator factory base          |
| `arithmetic_field`| fields.py        | `State → delta dict`           |
| `parametric_field`| fields.py        | Linear gain on one axis        |
| `clamp_field`     | fields.py        | Hard bounds on every key       |
| `smoothing_field` | fields.py        | Exponential decay              |


## v1.2.0 additions

The driver now exposes four public getters used by self-evolution
and any future orchestrator. Use these instead of reaching into
engine internals:

```python
engine.operators()           -> Tuple[Operator, ...]
engine.step_size()           -> float
engine.max_subdivisions()    -> int
```

The phase enumerator is exposed through `from minxg.driver import
EnginePhase` and printed by the bundled `engine.phase` property.

Hook into phase transitions with:

```python
engine.on_phase(lambda prev, new: ...)
```
