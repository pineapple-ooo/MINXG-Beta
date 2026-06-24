# TIDAL_LOCK

> C/C++/Go acceleration for the hot path.
> See [ARCHITECTURE.md](ARCHITECTURE.md) for context.

## Architecture

```
┌─────────────────────────────────────────────┐
│            Python (high-level control)      │
│  ┌───────────────────────────────────────┐  │
│  │  minxg/_tidal_lock_bridge.py         │  │
│  │  ctypes-based Python wrapper         │  │
│  └───────────────────────────────────────┘  │
│                     │ ctypes                │
│  ┌───────────────────────────────────────┐  │
│  │  c_core/libminxg_tidal.so             │  │
│  │  C implementation of 11 functions     │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## The 11 locked functions

1. `tl_isg_hash` — ISG structure hash (xxhash-based)
2. `tl_ncd_compute` — NCD between two strings
3. `tl_ncd_batch` — Batch NCD computation
4. `tl_zstd_compress` — zstd compression
5. `tl_zstd_decompress` — zstd decompression
6. `tl_xxhash3` — xxhash3 64-bit hash
7. `tl_phase_embed` — 32-dim phase-space embedding
8. `tl_drift_compute` — Phase-space drift detection
9. `tl_persistence_score` — Persistence scoring
10. `tl_behavior_classify` — Classify behavior to nearest SIC
11. `tl_entropy_compute` — Shannon entropy with zstd compression

## Performance

| Function | Pure Python | Tidal Lock C | Speedup |
|----------|-------------|--------------|---------|
| NCD (1KB text) | 850 μs | 12 μs | 70x |
| Phase embed | 1.2 ms | 45 μs | 27x |
| zstd compress | 320 μs | 18 μs | 18x |
| Drift compute | 2.1 ms | 78 μs | 27x |
| xxhash3 | 0.5 μs | 0.02 μs | 25x |

## Building

```bash
cd c_core
make
```

Produces `libminxg_tidal.so` (Linux), `.dylib` (macOS), or `.a` (static).

## Loading

The Python wrapper auto-detects:

```python
from minxg._tidal_lock_bridge import TidalLock, get_tidal_lock

tl = get_tidal_lock()
if tl.is_loaded:
    ncd = tl.ncd_compute(a, b)
```

## Termux/Android

`core_native.py` auto-detects Termux and copies any prebuilt `.so`
to a writable location before loading (bypasses Android's linker
namespace restriction).

## Why "Tidal Lock"?

A tidal lock in celestial mechanics is a stable state where one body's
rotation matches its orbital period. The C core and Python wrapper are
"locked" into stable interfaces — algorithm choices are pinned, the
function signatures are guaranteed, the performance is deterministic.

## Reference

- `c_core/` — C source code
- `minxg/_tidal_lock_bridge.py` — Python bridge
- `src/ai/memory/tidal_lock_bridge.py` — legacy alias
