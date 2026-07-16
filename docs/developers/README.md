# MINXG Developer Guide

> Assumptions: you can read Python, you're comfortable with async/await,
> and you want to add something useful without fighting the framework.

## The five-pillar layout

```
minxg/
├── five_pillars/
│   ├── scalar/       # math + text ops
│   ├── aggregate/    # encoding, crypto, ML templates
│   ├── io/           # filesystem, network, web
│   ├── dispatch/     # shell, ADB, system admin
│   ├── transform/   # AI tools, state sessions
│   └── polyglot/     # Rust, C++, R, Julia, Datalog adapters
├── math_pillar/      # ga, cat, infogeo, topo, chaos, fiber (pure math)
└── core/             # BaseWorker, ToolDef, ToolChainExecutor
```

**Rule zero: pillars don't talk to each other.** Each pillar imports only
`minxg.base`. Sibling imports are fine within a pillar. Cross-pillar imports
are a bug.

---

## Adding a new worker (TL;DR)

1. Subclass `BaseWorker`
2. Decorate public methods with `@tool`
3. Register it in `minxg/five_pillars/<pillar>/__init__.py`
4. Write at least one test
5. Run `pytest tests/` — green means done

```python
from minxg.base import BaseWorker, tool

class DiskSpaceWorker(BaseWorker):
    """Checks disk space. Shocking, I know."""

    @tool
    def disk_usage(self, path: str = "/") -> dict:
        """Return disk usage for the given path."""
        import shutil
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb":  round(usage.used  / (1024**3), 2),
            "free_gb":  round(usage.free  / (1024**3), 2),
            "percent":  round(usage.used / usage.total * 100, 1),
        }
```

---

## The `@tool` decorator

```python
@tool(description="What this does", aliases=["legacy_name"])
def my_method(self, arg1: str, arg2: int = 10) -> dict:
    ...
```

- `description` becomes the tool's docstring in the AI gateway
- `aliases` registers alternative names (for back-compat)
- Return `dict` — serialized to JSON for the AI
- Raise `ValueError` for bad input (MINXG handles it, not the AI)

---

## ToolChainExecutor — one AI call, N tool executions

Instead of making the AI call a tool, then calling the AI again, then another
tool... you can pack multiple tool calls into one LLM response:

```python
from minxg.core.tool_chain import ToolChainExecutor, ToolStep, TOOL_REGISTRY

steps = [
    ToolStep(tool="self_evolution.evolution_record",  params={"event": "feature"}),
    ToolStep(tool="binary_toolbelt.elf_hash",          params={"path": "/bin/ls"}),
]
executor = ToolChainExecutor(TOOL_REGISTRY, max_parallel=2)
result = await executor.execute(steps)
```

- Steps run sequentially by default; set `max_parallel` to run independent
  steps concurrently
- `condition` on a step makes it conditional on prior results
- `await_user` pauses for human confirmation before running
- Falls back to sequential if the LLM doesn't produce a plan

---

## The Rust bridge — calling Rust from Python

```python
from minxg.rust_bridge import signal_energy, lyapunov_logistic

# Rust FFT (falls back to pure Python if .so not built)
energy = signal_energy([0.1, 0.2, 0.3])

# Lyapunov exponent — λ > 0 means chaos
result = lyapunov_logistic(0.5, 3.7)  # r=3.7 → chaotic
result = lyapunov_logistic(0.5, 3.2)  # r=3.2 → periodic
```

To build the Rust .so (optional, falls back gracefully if absent):

```bash
cd rust_core && cargo build --release
# produces: rust_core/target/release/libminxg_rust.so
```

---

## Testing

```bash
# Run everything
pytest tests/ -q

# Run just the relevant tests
pytest tests/test_self_evolution.py tests/test_cli_tui.py -v

# Watch mode
pytest tests/ -q --watch
```

Tests clean `~/.minxg/evolution.jsonl` before running — the self-evolution
log is cleared so each test gets a fresh slate.

---

## Common gotchas

1. **Don't `await` inside a non-async method** — if your `@tool` method doesn't
   need I/O, keep it sync. If it does, make it `async def`.
2. **Return dicts, not strings** — the AI gateway serializes dicts to JSON.
   A bare string becomes `{"result": "your string"}`.
3. **Pillar imports** — don't reach across pillars. If two pillars need the
   same thing, it belongs in `minxg.base`.
4. **Evolution log** — each test run clears `~/.minxg/evolution.jsonl`. If you're
   running `minxg` interactively, the log just keeps growing. That's normal.
5. **Rust .so missing** — MINXG falls back to pure Python automatically.
   Everything works, just slower. Build the .so when you need the speed.

---

*See [ARCHITECTURE.md](../ARCHITECTURE.md) for the full picture.*