# MINXG-Beta — Developer Index

> **Audience:** people who want to extend MINXG-Beta, port it, audit it,
> or understand how the 376-operator catalog was put together. Read
> linearly if you're new; jump straight to the file you need.

## 1 · Architecture and mental model

| File | What it covers |
|------|----------------|
| [`architecture.md`](architecture.md)               | Top-down system diagram, the *capability window* plugin trick, the seven layers |
| [`operator-registry.md`](operator-registry.md)     | How the 376 numbers stay at 376 forever (idempotency, dedup, CI guard) |
| [`six-pillars.md`](six-pillars.md)                 | GA / CAT / IG / TOPO / CHAOS / FIBER — *why these six*, *why this order* |
| [`native-runtimes.md`](native-runtimes.md)         | `c_core/` / `cpp_core/` / `go_core/` boundaries, Termux `ctypes` quirk |
| [`extension-capability-window.md`](extension-capability-window.md) | Bootstrap a new pillar **without touching `minxg/` code** |

## 2 · Extending the framework

| File | What it covers |
|------|----------------|
| [`extending.md`](extending.md)                     | Adding an operator, adding a worker, adding a pillar, adding a tool |
| [`plugin-format.md`](plugin-format.md)             | The `extension.toml` manifest, hot-reload, the `_capabilities/*.py` contract |
| [`config-and-state.md`](config-and-state.md)       | `config/minxg.yaml`, `minxg.get(key)`, persistence layer overview |

## 3 · Native acceleration

| File | What it covers |
|------|----------------|
| [`native-runtimes.md`](native-runtimes.md)         | How C/C++/Go cores are detected and dispatched |
| [`building-native.md`](building-native.md)         | Build cmds per platform, debugging shared-library load failures |
| [`termux-quirks.md`](termux-quirks.md)             | `ctypes` namespace restriction, `xxhash` / `orjson` availability matrix |

## 4 · Self-evolution, safety, CI

| File | What it covers |
|------|----------------|
| [`self-evolution.md`](self-evolution.md)           | The BIE engine: 10 algorithms, ISG, NCD, Tidal Lock |
| [`anti-loop-guard.md`](anti-loop-guard.md)         | `guard.py` progressive severity, how it interacts with the registry |
| [`ci.md`](ci.md)                                   | GitHub Actions matrix (3.11 / 3.12 / 3.13), the 376-assertion, ruff gate |

## 5 · Reference

| File | What it covers |
|------|----------------|
| [`operator-id-table.md`](operator-id-table.md)     | ID ranges, who owns them, how to claim a new range |
| [`changelog-policy.md`](changelog-policy.md)       | How to write a CHANGELOG entry, what triggers a minor bump |
| [`release-process.md`](release-process.md)         | From commit to `pip install -U minxg-beta` |

---

## A note on the name

The Python package is **`minxg`** (lowercase, no `-beta`, by import-name
convention). The product name is **`MINXG-Beta`**. Don't get them
confused when reading old docs — they refer to the same code.
