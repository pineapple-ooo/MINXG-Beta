# MINXG vs Hermes Agent — Benchmark (v0.18.2 vs Hermes 2.3.x)

*Both MIT-licensed. MINXG builds on prior art; this is engineering, not marketing.*

---

## TL;DR

| Dimension | Hermes Agent | MINXG | Winner |
|-----------|-------------|-------|--------|
| Languages in core | 1 (Python) | **7** (Rust/C++/R/Julia/Datalog/Wasm/Go) | **MINXG** |
| Gateway platforms | 20 | **19 + own gateway = 20** | Tie |
| Tool files | 96 | **743 `@tool` methods** (facade-collapsed to ~200 visible) | **MINXG** |
| Tool chain (1 LLM call → N tools) | ❌ per-call | **✓ ToolChainExecutor** | **MINXG** |
| Rust math (FFT/Kalman/Lyapunov) | ❌ | **✓ sub-ms** | **MINXG** |
| Lock-free C++ ringbuf | ❌ | **✓ SPSC zero-copy** | **MINXG** |
| Self-evolution loop | ❌ | **✓ TwinEngine + FieldForge** | **MINXG** |
| Math pillars | 0 | **6** (GA/cat/infogeo/topo/chaos/fiber) | **MINXG** |
| Tests | — | **713 passed** | **MINXG** |
| Architecture | Python monolith | 3-tier + 7 pillars + polyglot adapters | Style |

> Hermes is a solid generalist. MINXG is a specialist that happens to also be a generalist.

---

## 1. Language diversity

**Hermes:** Pure Python. Clean, simple, everything talks to everything.

**MINXG:** Seven languages, each doing what it does best:

| Language | Job | Performance |
|----------|-----|------------|
| Rust | Math ops, FFT, signal processing, hash, dot product | **~0.1–1ms** |
| C++ | Lock-free SPSC ring buffer, zero-copy memory guards | **cache-line correct** |
| R | Cold statistics, bootstrapping, time series | **CRAN ecosystem** |
| Julia | JIT-hot numerical loops, PDEs | **MATLAB-grade speed** |
| Datalog | Logic rules, constraint solving | **recursive without the pain** |
| Go | HTTP services, CLI wrappers | **boring + correct** |
| WASM | Browser-adjacent compute | **runs anywhere** |

The Rust core (`libminxg_rust.so`) is optional — MINXG ships a pure-Python
fallback for every operation. Build the `.so` when you need the speed.

---

## 2. Gateway platforms

**Hermes:** 20 platforms (Telegram, Discord, Slack, WhatsApp, iMessage,
Signal, Matrix, Teams, Email, SMS, LINE, SimpleX, ntfy, Google Chat, Home
Assistant, DingTalk, Feishu, WeCom, Weixin/Wechat, Raft, API Server, Webhooks).

**MINXG:** 19 channels via `unified-channel` adapter + its own gateway.
Same surface, but every message passes through MINXG's tool chain before delivery.

```
telegram · discord · slack · whatsapp · imessage · line
matrix · msteams · feishu · mattermost · googlechat · nextcloud
synology · zalo · nostr · bluebubbles · twitch · irc
```

MINXG's own gateway is OpenAI-compatible. Swap providers without touching tools.

---

## 3. Tool count

**Hermes:** 96 tool files, ~34 registered toolsets.

**MINXG:** 743 `@tool` method decorators across 56 workers.
Facade aliases collapse legacy flat names — visible surface is ~200 tools.
Direct callers (tests, gateway, imports) keep working unchanged. **Zero breaking changes.**

Pre-de-dup, operators totaled 656 `@tool` methods across 56 workers. After
facade consolidation, the surface is lean but the depth is unchanged.

---

## 4. ToolChainExecutor (the 10ms difference)

**Hermes:** One LLM call → one tool → one LLM call → next tool.
Typical latency: **80–200ms per round-trip** × N tools.

**MINXG:** One LLM call → plan (JSON array of steps) → ToolChainExecutor
dispatches all steps. **15–20ms total** for 2 independent steps, 0 AI calls.

```python
from minxg.core.tool_chain import ToolChainExecutor, ToolStep, TOOL_REGISTRY

steps = [
    ToolStep(tool="self_evolution.evolution_record", params={"event": "feature"}),
    ToolStep(tool="binary_toolbelt.elf_hash", params={"path": "/bin/ls"}),
]
result = await ToolChainExecutor(TOOL_REGISTRY, max_parallel=2).execute(steps)
# 15ms, 0 LLM calls
```

Conditional branches (`condition`) and loops (`loop: {max_iterations: N}`)
still trigger LLM callbacks — but sequential chains of N tools cost 1 call, not N.

---

## 5. Math pillars (the overachievers)

**Hermes:** Zero. Pure Python.

**MINXG:** Six mathematical pillars, each owning a stable operator ID range:

| Pillar | ID range | What it gives you |
|--------|----------|-------------------|
| `ga` | 5000–5499 | Geometric algebra: rotors, blades, line/plane intersections |
| `cat` | 4000–4499 | Category theory: morphisms, functors, monads |
| `infogeo` | 7000–7499 | Information geometry: Fisher metric, KL divergence |
| `topo` | 8000–8499 | Algebraic topology: persistent homology, Mapper graphs |
| `chaos` | 8500–8999 | Dynamical systems: **Lyapunov exponents**, attractors, maps |
| `fiber` | 6000–6499 | Fiber bundles: connections, parallel transport |

Each pillar is isolated. Swapping an operator doesn't recompile anything else.
IDs are permanent — old code keeps resolving.

---

## 6. Algorithms (what MINXG has that Hermes doesn't)

| Algorithm | Location | What it does |
|-----------|----------|-------------|
| **Lyapunov exponent** | Rust `signal.rs` + Python bridge | λ > 0 → chaos detected; Rosenstein method |
| **Fixed-point iteration** | Python bridge | Solve x = g(x) by successive substitution |
| **Cooley-Tukey FFT** | Rust `signal.rs` | O(n log n) frequency analysis |
| **Haar DWT** | Rust `signal.rs` | Wavelet decomposition |
| **Kalman filter** | Rust `signal.rs` | 1D linear Kalman with `KalmanState` |
| **SPSC ring buffer** | C++ `ringbuf.hpp` | Lock-free single-producer/single-consumer, cache-line aligned |

---

## 7. Self-evolution

**Hermes:** Skill accumulation over sessions (curator, kanban, cron).

**MINXG:** The **DriverEngine watches itself fail** and auto-replaces operators:

```
DriverEngine.step()
    │
    ├─ FailureTour — detects NaN / blown amplitude
    │
    ├─ FieldForge — asks contracts registry for same capability
    │
    ├─ TwinEngine — shadow clone tests the candidate
    │
    └─ replace_operator() — swaps in the winner
```

Replacements land atomically at end-of-cycle. Max 3 per cycle. The loop is
**purely advisory** — it never mutates mid-step.

---

## 8. Architecture philosophy

**Hermes:** Python monolith with plugin/extension surface. Clean, well-documented.
Everything in `hermes_cli/`, `agent/`, `gateway/`, `tools/`.

**MINXG:** Three-tier architecture with pillar isolation:

```
Layer 1: multiligua_cli / gateway      ← user-facing
Layer 2: multiling/                    ← agent brain
Layer 3: minxg/                        ← five pillars + math pillars + polyglot
Layer 4: rust_core · cpp_core · go_core ← optional native acceleration
```

Pillars only import `minxg.base`. No cross-pillar imports. Three mechanical
rules make MINXG **refactorable without cascade breaks:**
1. No relative imports across pillars
2. Capability-based dispatch (Cells advertise, callers don't import)
3. Stable operator IDs — new ones append, never renumber

---

## What Hermes does better

- **Desktop app** — native Electron (macOS/Linux/Windows), not just TUI/web
- **OAuth + credential pooling** — multiple API keys rotating automatically
- **Memory backends** — Honcho/Mem0 integration, not just SQLite
- **MCP server** — runs as stdio MCP server other tools can connect to
- **Curator (skill consolidation)** — aux-model skill merging, off by default
- **Documentation** — 53K-char skill spec, comprehensive user guides
- **Profiles** — fully isolated multi-tenant instances

MINXG is younger. These are honest gaps.

---

## Bottom line

- If you want **generalist flexibility, great docs, and a polished desktop app**: use Hermes
- If you want **raw polyglot performance, math muscle, and tool chains that don't burn LLM calls**: use MINXG

MINXG isn't trying to be Hermes. It's trying to be the version of Hermes that
read the Sedgewick algorithms book and learned Rust on the weekends.

---

*Last updated: v0.18.2*
*Canonical source: `docs/BENCHMARK.md`*