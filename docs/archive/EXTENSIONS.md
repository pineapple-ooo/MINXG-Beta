# EXTENSIONS

> Build your own operators, workers, and even mathematical pillars.
> For the architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 1 · Add a new operator

The simplest extension. Operators live in the relevant pillar's
`operators_*.py` file, but for custom operators you can also register
at runtime:

```python
from minxg.operators import Operator, OPERATOR_REGISTRY

def my_function(x, y):
    return x * x + y * y

OPERATOR_REGISTRY.register(Operator(
    op_id=10000,
    name="my_squared_sum",
    category="custom",
    description="Sum of squares",
    input_types=["number", "number"],
    output_type="number",
    is_pure=True,
    fn=my_function,
))

op = OPERATOR_REGISTRY.get_by_name("my_squared_sum")
print(op(3, 4))
```

## 2 · Add a new worker

Workers are higher-level than operators — they expose multiple tools
and manage state. Use the `@tool` decorator:

```python
from minxg.base import BaseWorker, tool

class MyWorker(BaseWorker):
    name = "my_worker"

    @tool(description="Compute sum of squares")
    def sum_squares(self, x: float, y: float) -> float:
        return x * x + y * y

    @tool(description="Format a greeting")
    def greet(self, name: str, language: str = "en") -> str:
        if language == "zh":
            return f"你好,{name}!"
        return f"Hello, {name}!"

worker = MyWorker()
```

## 3 · Add a new mathematical pillar

To add a 7th pillar (e.g., Spectral Theory, Game Theory):

1. Create `minxg/<your_pillar>/__init__.py`
2. Create `minxg/<your_pillar>/operators_<pillar>.py` with a
   `register_<pillar>_operators()` function
3. Add the pillar to `minxg/__init__.py` auto-registration:

```python
try:
    from . import <your_pillar>
    from .<your_pillar> import operators_<pillar> as _<pillar>_ops
    <PILLAR>_OPERATORS = _<pillar>_ops.<PILLAR>_OPERATOR_COUNT
except ImportError as e:
    <PILLAR>_OPERATORS = 0
```

4. Update `config/minxg.yaml` to add your pillar
5. Add an ID range in [PROJECT_INDEX.md](PROJECT_INDEX.md) § 4
6. Add `minxg/<your_pillar>/README.md` (+ .zh.md / .ja.md / .ko.md)

## 4 · Create a full extension package

Drop into `extensions/user/<your_extension>/`:

```
extensions/user/my_extension/
├── extension.yaml
└── worker.py
```

```yaml
# extension.yaml
name: my_extension
version: 1.0.0
author: Your Name
description: A custom extension
entry_point: my_extension.worker:worker
dependencies: []
```

```python
# worker.py
from minxg.base import BaseWorker, tool

class MyWorker(BaseWorker):
    name = "my_extension"

    @tool(description="My custom tool")
    def my_tool(self, x: str) -> str:
        return f"Processed: {x}"

worker = MyWorker()
```

The extension auto-loads on startup.

## 5 · Hot reload

```python
from minxg.hotreload import HotReloadWorker
hot = HotReloadWorker()
hot.enable()
```

When a file in `minxg/` or `extensions/` changes, the system
auto-reloads it.

## 6 · Add a new translation

Each user-facing doc has 4 language versions:
- `<doc>.md` (English, canonical)
- `<doc>.zh.md` (Simplified Chinese)
- `<doc>.ja.md` (Japanese)
- `<doc>.ko.md` (Korean)

To translate, copy the English version and translate the content
(keep code blocks, paths, and IDs unchanged).

## Reference

- `minxg/operators.py` — `Operator`, `OPERATOR_REGISTRY`
- `minxg/base.py` — `BaseWorker`, `@tool` decorator
- `minxg/fiber/` — copy this to add a new pillar
- `extensions/builtin/` — example extensions
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture
