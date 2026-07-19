# MINXG Architecture

This exists because the directory names are confusingly similar
(`minxg/`, `multiling/`, `multiligua_cli/`) and nothing previously
explained how they relate. If you're new here, read this before
grepping around blind.

## The five layers

```
multiligua_cli/   CLI + chat UI          "the app"
        │
agent/             conversation loop      "the reasoning loop"
        │
multiling/         AI orchestration       "the engine"
        │
tools/             chat-agent tools       "what the agent can call"
        │
minxg/             math + MCP workers     "the science + the MCP surface"
```

- **`multiligua_cli/`** — everything a user actually runs: `main.py`
  (argparse entry point + every `minxg <command>` dispatch), the TUI
  chat, `features.py`, `skill_cli.py`, `gateway_cli.py`, themes,
  memory viz, cost tracking. If you're adding a new `minxg <verb>`
  command, this is where it goes.
- **`agent/`** — the actual agentic loop: `conversation_loop.py` decides
  when to call a tool vs. respond, `iteration_budget.py` bounds how
  many tool-call round-trips a single turn can take. Small and focused
  on purpose.
- **`multiling/`** — the runtime underneath the CLI: `orchestrator.py`
  talks to AI providers, `platform_cap.py` is the platform-capability
  detector (what's safe to enable on this OS/device), `toolsets.py` is
  metadata describing the `tools/` registry for the CLI's `minxg tools`
  view, `ipc_server.py` / `workers_runner.py` back the gateway.
- **`tools/`** — the function-calling surface the chat agent actually
  invokes mid-conversation: `file_tools.py`, `terminal_tool.py`,
  `web_tools.py`, `system_tools.py`, `cronjob_tools.py`,
  `skill_manager_tool.py`, `delegate_tool.py`, all self-registering
  into `tools/registry.py` at import time. `minxg doctor`'s "active
  tools" count is this registry.
- **`minxg/`** — two things share this package:
  1. `minxg/five_pillars/` + friends (`ga`, `cat`, `infogeo`, `fiber`,
     `chaos`, ...) — the math/science operator library (geometric
     algebra, category theory, information geometry, ...). Genuinely
     independent of the agent/CLI stack; usable as a standalone Python
     library (see `examples/`).
  2. `minxg/workers/` + `minxg/mcp_server.py` — a **second**,
     independent tool surface exposed over MCP (Model Context
     Protocol) rather than the chat-agent's own function-calling. Some
     categories overlap in *domain* with `tools/` (both have file
     operations, for instance) but serve different callers — an
     external MCP client (Claude Desktop, Cursor, ...) talks to
     `minxg/workers/`, MINXG's own chat loop talks to `tools/`.
  3. `minxg/core_ops/` — shared logic used by *both* of the above where
     they'd otherwise duplicate something safety-relevant (e.g.
     `file_safety.py`'s blocked-path/binary-file checks, used by both
     `tools/file_tools.py` and `minxg/workers/file/file_workers.py`;
     `skill_registry.py`, used by both `tools/skill_manager_tool.py`
     and `multiligua_cli/skill_cli.py`). **If you're duplicating a
     safety check across two entry points, it probably belongs here
     instead.**

## Everything else

- **`gateway/`** — the OpenAI-compatible HTTP API (`gateway/server.py`)
  plus the multi-channel messaging adapters (`gateway/channels.py` +
  `channel_telegram.py` / `channel_discord.py` / `channel_slack.py`).
  Runs standalone via `minxg gateway`.
- **`extensions/`** — user-installable *executable* plugins (as opposed
  to `skills/`, which are markdown-only). `extensions/loader.py`
  discovers/enables/disables them; `extensions/package_cli.py` backs
  `minxg ext ...`. Built-ins live in `extensions/builtin/`.
- **`skills/`** — markdown instruction bundles MINXG ships with, in
  `<category>/<name>/SKILL.md` layout. `minxg skill ...` (backed by
  `minxg/core_ops/skill_registry.py`) can install more from a local
  path, a git URL, or a catalog (`skills/catalog.json`).
- **`src/ai/`** — a smaller, older utility layer (Termux notifications,
  a safety guard module, a couple of memory helpers). Not part of the
  five-layer stack above; check call sites before assuming it's dead —
  some of it (`src/ai/notify/termux.py`) is actively used by the
  Android/Termux path.
- **`c_core/`, `cpp_core/`, `rust_core/`, `go_core/`, `java_core/`,
  `ts_core/`** — polyglot bridges for the math subsystem. `minxg
  doctor` reports which toolchains are actually installed on your
  machine; most of these are optional acceleration, not required to
  run MINXG.
- **`config/`** — YAML configs + their schemas (`gateway.yaml`,
  `minxg.yaml`, ...).
- **`docs/`, `examples/`, `tests/`, `scripts/`** — what they say. Every
  bug this file's neighboring renovation pass fixed came with a
  regression test in `tests/`; keep that going.

## Two tool registries, on purpose

The most common "wait, why are there two of these" question is
`tools/` vs `minxg/workers/`. They're not accidental duplication — they
serve genuinely different callers (in-process chat agent vs. external
MCP client) with different calling conventions (JSON-string-returning
handler functions vs. `Worker.execute()` classes). Where they overlap
in *domain*, the fix isn't merging them into one interface — it's
making sure the actual logic underneath is shared (`minxg/core_ops/`),
so a safety fix in one place protects both. Do that before reaching
for a bigger refactor.

## Why this file, not a physical reorg

A full move of ~440 Python files into a cleaner tree was on the table
for this pass and got cut deliberately: every import statement,
`__init__.py`, and packaging config in the repo would need updating in
lockstep, verified end-to-end, with a much higher chance of a subtle
breakage this pass's test suite wouldn't catch (import cycles,
`sys.modules` assumptions some tests already lean on — see
`CHANGELOG.md`'s 0.18.4 entry for one that bit a test file directly).
Documenting the real shape of the codebase gets contributors unblocked
today without that risk. If a physical reorg happens later, it should
be its own dedicated pass with its own test-by-test verification, not
a side effect of an unrelated feature change.
