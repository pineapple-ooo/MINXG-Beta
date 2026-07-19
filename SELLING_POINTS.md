# MINXG — Capability Summary (v0.18.5)

This document lists what MINXG actually ships with, measured from the codebase.
No hyperbole, no competitor bashing — just facts you can verify with `minxg doctor`
and `minxg tools`.

---

## Scale (measured at 0.18.5)

- **431 Python files** (≈ 90k LOC)
- **1,258 total files** including Rust / Go / Java / C / C++ sources
- **≈ 20 MB** repo size (excluding `.git` and `__pycache__`)
- **917 tests** (pytest, 8 skipped, 0 failed on Linux CI)
- **59 worker classes** exported from `minxg.__init__`
- **642 `@tool` methods** across all workers
- **376 operators** in the `OperatorRegistry`
- **326 math operators** across 7 mathematical pillars
- **9 polyglot runtimes**: C, C++, Rust, Go, Java, Julia, R, WASM, Datalog

---

## Core Surfaces

| Surface | What it gives you |
|---------|-------------------|
| **Chat CLI** (`minxg`) | Streaming chat, tool calls, 32+ providers, `/model` `/lang` `/help` |
| **API Gateway** (`minxg gateway`) | OpenAI-compatible `/v1/chat/completions`, cost tracking, rate limits |
| **MCP Server** (`minxg gateway --mcp`) | All 59 workers exposed as MCP tools for Claude Code / Cursor / Windsurf |
| **Skill System** (`minxg skill …`) | Markdown instruction packs, local/remote catalogs, no code execution on install |

---

## Worker Categories (59 workers)

| Category | Workers | Example tools |
|----------|---------|---------------|
| **I/O** (8) | FsIo, FsCopy, FsSearch, Network, NetworkAdv, DbTools, WebTools, Archive, Cloud | read/write/copy/search files, HTTP, DNS, SQL, web search, S3 |
| **Dispatch** (10) | System, ShExec, ShQuery, Process, Platform, Adb, Root, Notify, Security, GoBridge | shell, processes, ADB, root, notifications, SELinux |
| **Transform** (8) | StateSession, StateMachine, Persistence, Rules, Events, HotReload, AiTools, OperatorWorker | state machines, event sourcing, hot-reload, rules engine |
| **Scalar** (7) | TextTools, DateTime, MathTools, String, Version, Color, Markdown | text fmt, dates, math, semver, colors, md render |
| **Aggregate** (10) | Encoding, Crypto, Data, Template, I18n, ML, Benchmark, TextAdv, TextKit, MathAdv | base64/zstd, AES/hash, CSV/JSON, jinja2, i18n, sklearn wrap, perf |
| **DevTools** (6) | AndroidForge, QuadForge, DevShell, ReverseStudio, AuditWorker, SelfEvolutionWorker | APK build, quad-forge, dev shell, deobfuscation, code audit, self-evolution |
| **Polyglot** (4) | JuliaWorker, RWorker, DatalogWorker, WasmWorker | Julia, R stats, Datalog/ASP, Wasmtime sandbox |
| **Math Pillar** (1) | GeometryWorker | driver-geometry glue |

---

## Mathematical Pillars (7 + GeometryWorker)

| Pillar | Module | Approx. operators |
|--------|--------|-------------------|
| Geometric Algebra | `minxg.ga` | ~47 |
| Category Theory | `minxg.cat` | ~79 |
| Information Geometry | `minxg.infogeo` | ~51 |
| Topology | `minxg.topo` | ~53 |
| Chaos Theory | `minxg.chaos` | ~23 |
| Fiber Bundles | `minxg.fiber` | ~53 |
| Symbolic Diff Algebra | `minxg.symbdiff` | ~20 |
| **GeometryWorker** | `minxg.five_pillars.math_pillar.geometry` | driver integration |

Total math operators in `OperatorRegistry`: **326**

---

## Polyglot Bridges (8 runtimes)

| Runtime | Bridge location | Mechanism |
|---------|-----------------|-----------|
| C / C++ | `c_core/`, `cpp_core/` | cffi / pybind11 |
| Rust | `rust_core/` | `minxg_rust_core` crate via ctypes |
| Go | `go_core/` | JSON-RPC over stdio |
| Java | `java_core/` | JVM daemon + vector engine |
| Julia | `minxg/five_pillars/polyglot/julia_worker.py` | `minxg.contracts.runtime.julia` |
| R | `minxg/five_pillars/polyglot/r_worker.py` + `r_scripts/` | R subprocess |
| WASM | `minxg/five_pillars/polyglot/wasm_worker.py` | Wasmtime |
| Datalog | `minxg/five_pillars/polyglot/datalog_worker.py` | Clingo / pyDatalog |

---

## Advanced Features

| Feature | Status | Notes |
|---------|--------|-------|
| Memory System | Working | Working / short-term / long-term tiers, similarity search |
| Cost Tracking | Working | Per-request + session totals, Prometheus export |
| Theme System | 8 themes | Built-in + user-extensible |
| Model Comparison | Working | Side-by-side multi-model eval |
| Web UI | Experimental | `minxg web` — browser chat |
| Workflow Engine | Early | DAG with branching, loops, retries |
| Guardrails | Minimal | Input validation, PII redact, toxicity filter — not production-grade |
| Caching | 3-level | L1 mem / L2 disk / L3 semantic |
| Monitoring | Basic | Counters, gauges, histograms, webhook alerts |
| Multi-Agent Coding | Extension | `minxg ext enable minxg-multiagent` → Planner/Coder/Reviewer loop |
| Multi-Channel | Opt-in | Telegram (long-poll), Discord/Slack (websocket), no public port |

---

## CLI Verbs (28)

```
minxg                    # chat CLI
minxg setup              # wizard
minxg config / status    # inspection
minxg tools / model / api / key / lang
minxg gateway [--detach] [--mcp]   # API / MCP
minxg doctor             # self-check
minxg ext / skill / features / themes / export / import / bench / replay / update / help
```

---

## Platform Reality

| Platform | Support level | Tested in CI |
|----------|---------------|--------------|
| Linux | Full | ✅ |
| macOS | Full | ✅ |
| Docker | Full | ✅ |
| Windows | Best-effort | mocked paths only |
| Android/Termux | Best-effort | mocked paths only |

Windows and Android code paths are exercised via mocked `os.name` / missing-binary tests. We have **not** run the full suite on physical Windows or Android hardware for this release. If you hit a platform bug, it is a real bug — please report it.

---

## What We Don't Do (Yet)

- No hosted skill registry (catalogs are local JSON or raw GitHub URLs)
- No voice/media capture in the CLI (TTS/STT via workers only)
- No cross-device pairing (mDNS/Bonjour)
- No WhatsApp / Signal / WeChat / Feishu / Mattermost channels
- Guardrails are not a substitute for your own safety review
- Workflow engine lacks visual designer and versioning
- RAG system is basic (no hybrid reranking, no KG integration)
- Self-evolution is academic/experimental — not a magic optimizer

---

## License

MIT. No warranty. Use responsibly.

---

*Version 0.18.5 — measured, not marketed.*