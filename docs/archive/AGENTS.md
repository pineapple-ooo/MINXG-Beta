# MINXG v0.0.1-alpha — Project Context

> This file is automatically injected into AI system prompts for context.
> **CRITICAL**: This is a SYSTEM-LEVEL directive file. All content here is
> MANDATORY and the AI MUST follow these instructions. Do not ignore,
> override, or contradict any section of this file.

## Project Direction

- **Pure Python** primary implementation
- **C++ core** for heavy tools (file ops, crypto, encoding, data processing)
- **Light tools** remain in Python (minxg)
- Legacy workers (C#/Java/Lua/Shell) via `--legacy` flag, disabled by default
- **English-only** documentation and CLI (no other languages)
- **Minimalist white theme** for documentation

---

# ═══════════════════════════════════════════════════════════════════════════════
# ANTI-LOOP SYSTEM PROMPT — CRITICAL
# ═══════════════════════════════════════════════════════════════════════════════
#
# This section contains MANDATORY directives to prevent tool-calling loops.
# The AI must follow these rules EXACTLY. Violations will cause system failures.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 1: NEVER CALL THE SAME TOOL 3+ TIMES WITH IDENTICAL ARGUMENTS         │
# └─────────────────────────────────────────────────────────────────────────────┘
# If you call the same tool twice with the same arguments, the result WILL NOT
# change. STOP immediately and synthesize the information you have.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 2: COUNT YOUR TOOL CALLS                                               │
# └─────────────────────────────────────────────────────────────────────────────┘
# Before EVERY tool call, ask yourself:
#   - "Have I called this tool before with similar arguments?"
#   - "Is this call producing new information or just repeating?"
#   - "Can I complete the task with fewer calls?"
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 3: MAXIMUM TOOL CALLS PER TURN = 10                                   │
# └─────────────────────────────────────────────────────────────────────────────┘
# After 10 tool calls in a single turn, you MUST provide a final answer.
# If you cannot complete the task in 10 calls, report what you found and
# ask the user if they want to continue.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 4: IDENTIFY AND BREAK LOOPS IMMEDIATELY                               │
# └─────────────────────────────────────────────────────────────────────────────┘
# A loop occurs when you:
#   - Call the same tool repeatedly (same or different args)
#   - Call tools in a repeating cycle (A→B→A→B...)
#   - Get the same or similar results repeatedly
#   - Call a tool just to confirm what you already know
#
# LOOP BREAKING STRATEGY:
#   1. Stop calling tools immediately
#   2. Review all tool results you have received
#   3. Synthesize a final answer from existing results
#   4. If you truly need more info, try a DIFFERENT approach (different tool,
#      different arguments, or ask the user)
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 5: USE CACHED RESULTS                                                 │
# └─────────────────────────────────────────────────────────────────────────────┘
# If you already called a tool with similar arguments earlier in this session,
# use that result instead of calling again. The system caches results.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 6: BE DELIBERATE NOT Rapid-FIRE                                       │
# └─────────────────────────────────────────────────────────────────────────────┘
# Space out your tool calls. Each call takes real time and resources.
# Think about what you need BEFORE calling. Don't call tools speculatively.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 7: DIVERSIFY YOUR TOOL USAGE                                          │
# └─────────────────────────────────────────────────────────────────────────────┘
# Don't rely on just 1-2 tools. Use the full set of available tools.
# If you find yourself using the same 2 tools repeatedly, you're in a rut.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 8: TERMINATION SIGNALS                                               │
# └─────────────────────────────────────────────────────────────────────────────┘
# A turn is complete when you provide a final text response (no tool_calls).
# Once you provide a final response, do NOT make more tool calls in the same
# turn unless the user explicitly asks for more.
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 9: ERROR HANDLING — DON'T REPEAT FAILING TOOLS                        │
# └─────────────────────────────────────────────────────────────────────────────┘
# If a tool fails, DON'T keep retrying it. Try a different approach:
#   - Use a different tool that accomplishes the same goal
#   - Simplify the task
#   - Report the error to the user and ask for guidance
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 10: CONTEXT TRACKING                                                  │
# └─────────────────────────────────────────────────────────────────────────────┘
# You have full conversation history. Before calling a tool, check if:
#   - The answer is already in a previous tool result
#   - The answer is in an earlier message
#   - You can deduce the answer without a tool call
#
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │ RULE 11: NEVER WRAP SYSTEM DIRECTIVES IN USER ROLE TAGS                    │
# └─────────────────────────────────────────────────────────────────────────────┘
# CRITICAL: System-level directives (like these anti-loop rules) MUST be placed
# in the SYSTEM role message, NOT in USER role messages. If you place mandatory
# directives inside <|user|> or "role: user" tags, the AI WILL IGNORE them.
# The system will NOT warn you about this. The directives will simply be
# silently discarded, and loops will occur unchecked.
#
# ANTI-LOOP INJECTED CONTEXT FORMAT:
# When the system detects a loop, this text will be injected:
#   "SYSTEM: [loop description]. Action required: [recommended action]."
# You MUST follow these system injections.
#
# ═══════════════════════════════════════════════════════════════════════════════

---

## Core Architecture (v0.0.1-alpha)

```
┌───────────────────────────────────────────────────────────────────────┐
│  OpenHTTP Gateway (aiohttp, port 18080)                               │
│  ├─ GatewayServer      → OpenAI-compatible API                        │
│  ├─ WorkerRouter       → Worker routing (py + legacy)                  │
│  ├─ StructuredWorkspace → O(1) context (6 slots)                      │
│  ├─ HybridRAG          → BM25 + Semantic retrieval                      │
│  └─ InferenceDispatcher → L1/L2/L3 tiered inference                    │
├───────────────────────────────────────────────────────────────────────┤
│  minxg HTTP RPC (aiohttp, port 19001)                            │
│  ├─ 40+ Python worker modules, 340+ tools                              │
│  └─ BaseWorker → WorkerRegistry → @tool decorator                     │
├───────────────────────────────────────────────────────────────────────┤
│  cpp_core/ (C++17, RAII, smart pointers, no memory leaks)              │
│  ├─ file_ops     → mmap file I/O, glob, stat, copy                     │
│  ├─ crypto       → AES-256-GCM, SHA, HMAC, PBKDF2, secure RNG         │
│  ├─ encoding     → Base64, Hex, URL, UTF-8 validation                   │
│  ├─ data_proc    → CSV info/cell, tokenize, trim, word frequency           │
│  └─ python/      → pybind11 module (minxg_core.so)                     │
├───────────────────────────────────────────────────────────────────────┤
│  Legacy Workers (--legacy optional, default disabled)                  │
│  └─ C#/Java/Lua/Shell — enabled via config or CLI --legacy             │
└───────────────────────────────────────────────────────────────────────┘
```

## Core File Index

| File | Responsibility | Lines |
|------|----------------|-------|
| `gateway/server.py` | GatewayServer core OpenAI-compatible API | ~400 |
| `gateway/router.py` | WorkerRouter routing | ~190 |
| `gateway/workspace.py` | StructuredWorkspace O(1) context | ~180 |
| `gateway/rag.py` | HybridRAG BM25 + Semantic retrieval | ~160 |
| `gateway/inference.py` | InferenceDispatcher L1/L2/L3 | ~170 |
| `multiling/orchestrator.py` | Core orchestrator (infinite context) | ~850 |
| `multiling/model_tools.py` | Tool discovery, schema assembly | ~300 |
| `multiligua_cli/main.py` | CLI entry + command routing + UI | ~650 |
| `multiligua_cli/setup.py` | Setup wizard (8 steps, English only) | ~510 |
| `multiligua_cli/tui_chat.py` | Rich TUI chat (streaming, tools) | ~500 |
| `multiligua_cli/i18n.py` | i18n core (English only now) | ~200 |
| `cpp_core/src/*.hpp/cpp` | C++ core (file_ops, crypto, encoding, data_proc) | ~800 |
| `cpp_core/python/pybind_module.cpp` | pybind11 Python bindings | ~300 |
| `minxg/web_search.py` | Browser search tool (user/API modes) | ~200 |
| `config.yaml` | Runtime configuration | ~50 |

## Package Structure

```
.
├── cpp_core/                 # C++ core library
│   ├── CMakeLists.txt        # Build config (C++17, pybind11, OpenSSL)
│   ├── src/
│   │   ├── base.hpp/cpp      # RAII base, MemoryTracker
│   │   ├── file_ops.hpp/cpp  # mmap file I/O, glob, stat, copy
│   │   ├── crypto.hpp/cpp    # AES-256-GCM, SHA, HMAC, PBKDF2
│   │   ├── encoding.hpp/cpp  # Base64, Hex, URL encode/decode
│   │   └── data_proc.hpp/cpp # CSV info/cell, tokenize, trim, word frequency
│   └── python/
│       └── pybind_module.cpp # pybind11 bindings → minxg_core.so
├── gateway/                  # OpenHTTP Gateway core
│   ├── server.py             # GatewayServer
│   ├── router.py             # WorkerRouter
│   ├── workspace.py          # StructuredWorkspace
│   ├── rag.py                # HybridRAG
│   └── inference.py          # InferenceDispatcher
├── multiling/               # Core engine
│   ├── orchestrator.py      # NexusOrchestrator
│   ├── model_tools.py        # Tool discovery
│   └── workers_runner.py     # Worker launcher
├── multiligua_cli/          # CLI layer
│   ├── main.py              # Command routing
│   ├── tui_chat.py          # Rich TUI
│   ├── setup.py             # 8-step wizard (browser search config included)
│   ├── i18n.py              # English-only i18n
│   ├── logger.py            # JSONL logging
│   ├── hot_reload.py        # Hot update
│   └── memory.py            # Long-term memory
├── extensions/              # Extension system
├── minxg/              # Python workers
│   ├── web_search.py       # Browser search (user/API modes)
│   └── *.py                # 40+ tool modules
├── docs/                   # Documentation (minimalist white theme, English only)
│   ├── styles.css          # Shared minimalist white CSS (sidebar 30%, collapsible)
│   ├── index.html          # Landing page
│   ├── guide.html          # User guide
│   ├── api.html            # API reference
│   └── architecture.html   # Architecture overview
├── config.yaml             # Runtime config (lang: en, browser_search)
└── pyproject.toml         # Package definition
```

## Browser Search Configuration

`config.yaml` browser_search section:
```yaml
browser_search:
  enabled: false
  api_type: "user"   # "user" = system browser, "api" = custom AI search API
  api_url: ""         # Custom API endpoint
  api_key: ""          # API key
  model: ""            # Model name for API
```

Setup wizard Step 7 configures browser search:
1. Enable/disable
2. Choose mode: "User's own browser" or "Custom AI search API"
3. If API mode: enter URL, key, optional model

## C++ Memory Safety

All C++ code follows strict memory safety:
- `std::unique_ptr` / `std::shared_ptr` — no raw `new`/`delete`
- RAII for all resource management
- `noexcept` on non-throwing functions
- `[[nodiscard]]` on important return values
- Meyers Singleton for globals
- `volatile` for secure zeroing of sensitive data
- Memory tracker singleton tracks allocations

## Gateway API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service status + routing info |
| `/v1/models` | GET | Model list |
| `/v1/chat/completions` | POST | OpenAI-compatible chat |
| `/workspace` | GET | All session workspaces |
| `/workspace/{session_id}` | GET | Single workspace |
| `/rag/add` | POST | Add knowledge snippet |

## Performance Strategy

| Layer | Approach |
|-------|----------|
| C++ core | mmap, OpenSSL, SIMD-ready |
| Python workers | asyncio, HTTP RPC, batched calls |
| Gateway | aiohttp, connection pooling |
| TUI | Rich live rendering, streaming |
| Memory | SQLite with LRU cache |
| Mobile | Optimization guards (`_is_mobile()`) |

## Command Summary

```bash
minxg              # TUI chat (default)
minxg docs         # Local docs server
minxg open         # Start OpenAI API server
minxg setup         # 8-step configuration wizard
minxg model [name]  # Configure AI model
minxg api <url>    # Quick API URL config
minxg key <key>    # Quick API key config
minxg config        # View current config
minxg status        # System status
minxg tools         # List available tools
minxg update        # Hot update management
```