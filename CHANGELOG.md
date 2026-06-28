# CHANGELOG

All notable changes to MINXG are documented in this file.

## [0.14.0] - 2026-06-28 - Polyglot expansion + gateway hardening + think UX + extension manifest

### Highlights
- **Open Gateway fully restored.** Rewrote `gateway/server.py` wiring so
  inference + RAG + router + runner + workspace all consume a single
  `GatewayConfig` (loaded from `minxg._config`); removed ad-hoc env-var
  forks. Added `gateway/channels.py` with a `ChannelManager`,
  `MemoryChannel`, and `HTTPChannel` so the ``channels`` section in
  ``config/gateway.yaml`` actually drives inbound surfaces (not only the
  REST server). Reference taken from ``/storage/emulated/0/文件/mmm/gateway``
  patterns (channel/manager), implemented fresh on top of MINXG's own
  config/state surfaces.
- **Chat "think" tags.** AI thinking is now wrapped in ``[thinking]...[/thinking]``
  in terminal/chat output so users can tell reasoning from response.
- **AI identity polish.** Removed the redundant "You:" prompt label from
  `multiligua_cli/interactive.py` and `multiligua_cli/terminal_chat.py`;
  the prompt now uses a neutral arrow (`▸`) matching `tui_chat.py`.
- **Wizard/config flicker killed.** The `MinxgMenu` widget in
  `multiligua_cli/wizard_ui.py` redraws in place with cursor-up/erase
  sequences instead of clearing the whole screen.
- **Centralised config bump.** VERSION lives in `minxg/_version.py` only;
  pyproject reads it via setuptools dynamic. Bumps are one-line edits and
  the `minxg/__init__.py` docstring now echoes the same value.
- **Polyglot activation.** Reactivated C/C++/Go paths via real subprocess
  bridges (`g++`/`clang++`, `go run`) that compile/run shipped source
  assets under ``minxg/contracts/runtime/assets``; added first-class adapters
  for WebAssembly (`.wat` + `wasmtime` / arithmetic emulator), R
  (``.R`` bridge + `jsonlite`), Datalog (``.lp`` + `clingo` / `pyDatalog`),
  and Julia (``.jl`` bridge + `JSON.jl`). Each adapter detects its own
  runtime availability and degrades cleanly when missing — manifest-driven
  discovery via `minxg polyglot-manifest`.
- **New experimental verbs.** ``minxg contract``, ``minxg polyglot-manifest``,
  ``minxg think`` toggle, and ``minxg ext-reload`` now work end-to-end.
  `ext-reload` uses the new `extensions.loader.rescan_all()` helper.
- **Self-evolved capability: MINXG Genesis Loop.** ``minxg genesis``
  runs propose → mutate → evaluate → crystallise and writes the winning
  candidate to ``~/.minxg/genesis/latest.py`` with a JSON report.

### Refactor
- Removed duplicate ``from __future__ import annotations`` in
  `gateway/server.py`.
- Normalised `minxg/contracts/runtime/_exec.py` shared helpers for
  subprocess-based language adapters.

### Updates since 0.14.0
- **Polyglot runtime install helpers.** New module
  `minxg/contracts/runtime/installer.py` exposes a 6-language install
  matrix (cpp / go / wasm / r / julia / datalog) with platform-aware
  recipes for ``termux`` / ``linux`` / ``macos`` / ``windows`` /
  ``unknown``. The module is pure-data by design: ``detect_runtime`` /
  ``plan_install`` / ``render_install_plan`` never launch subprocesses
  and ``run_install(..., apply=True)`` is opt-in via ``--apply`` so the
  user is never surprised by an unattended ``pkg install``. Re-exported
  through ``minxg.contracts.runtime`` so existing imports stay
  stable.
- **Two new [EXPERIMENTAL] verbs.** ``minxg runtime-plan [<lang>]``
  prints the install plan for one language (or every managed
  language when ``lang`` is omitted / ``all``). ``minxg
  runtime-install [<lang>] --apply`` runs *only* the chosen language's
  recipe via ``sh -c <cmd>`` with a 10-minute timeout, or stays a
  dry-run JSON view when ``--apply`` is absent. Both honour
  ``--platform`` so users on a Linux box can preview the Termux /
  macOS recipes and vice versa.
- **`minxg doctor` polyglot panel.** A new ``Polyglot runtimes``
  section reports every managed language's binary, availability, and
  install hint next to the existing ``Tool cap`` / ``Extensions``
  panels; it never escalates the doctor exit code past WARN when a
  runtime is missing (the verbosity matches the existing
  polyglot-manifest contract).
- **New tests.** ``tests/test_polyglot_runtime_installer.py`` (34)
  covers ``platform_id`` hermetic across all five platforms,
  per-language detect (R/jsonlite gate, Julia version probe, datalog
  clingo + pyDatalog fallback, wasm optional signal), install plan
  shape, ``run_install`` dry-run vs apply via the runner seam, and
  the doctor panel never returns FAIL. Full suite: 467 passed,
  1 skipped.
- **Twin emit now preserves the source function name.** The
  ``TwinConfig.function_name`` default flipped from the
  placeholder ``"twin_fn"`` to the empty-string sentinel
  ``""``, which makes :func:`minxg.twin.python_to_rust` fall back
  to ``fn.name`` on the Python side. The previous default forced
  every caller to wrap and rename — turning the round-trip test in
  ``tests/test_twin.py`` into a compile failure that was being
  silently turned into a skip. After the fix, the
  ``test_python_to_rust_emitted_function_compiles_when_rustc_present``
  case compiles a ``fn main { fn add(...) { ... } }`` template
  that, when ``rustc`` is on PATH, actually returns ``7`` from
  ``add(3, 4)`` instead of skipping.
- **Right-prefix temp dir on Android.** ``rustc -o /tmp/...``
  silently aborted on Termux (the symlinked ``/tmp`` can't host
  ``rustc``'s scratch subdirs); the test now writes the
  intermediate artefact into ``tempfile.mkdtemp(prefix="minxg_twin_")``
  so the same path used by ``minxg.contracts.runtime._exec.run``
  is the one ``rustc`` works in.
- **Full suite now skips 0 tests.** Before: 1 skipped (the
  silent-failure twin case). After: 468 passed, 0 skipped, 0
  failed.

## [0.13.2] - 2026-06-27 - Single source of truth for VERSION

### Refactor
- **Centralised the version number.** Added `minxg/_version.py` carrying
  the single source of truth (`VERSION`, `parse()`, `banner()`, `get_version()`).
- `pyproject.toml` now declares `dynamic = ["version"]` plus
  `[tool.setuptools.dynamic] version.attr = "minxg._version.VERSION"`,
  so setuptools reads the version from the SSoT at build time.
- `minxg/__init__.py` no longer holds its own literal; it imports
  `from ._version import VERSION as __version__`. `import minxg;
  minxg.__version__` still returns `"0.13.2"`.
- Rewrite of `tests/test_version_lock.py`: now distinguishes between
  the **code-path SSoT** (pytest imports `_version` directly and asserts
  code locations pull from it) and the **documentation surfaces** that
  must still echo the SSoT manually (`README.md`, `CHANGELOG.md`,
  `DEVELOPER.md` publish checklist).
- Bumping the version is now a single-file edit: change `VERSION` in
  `minxg/_version.py` and run `python -m pytest tests/test_version_lock.py`
  to confirm both code paths and doc surfaces propagate.

## [0.13.1] - 2026-06-26 - Version bump + GitHub release

### Release
- Bumped version lock across `pyproject.toml`, `minxg/__init__.py`,
  `README.md`, and `CHANGELOG.md` to **0.13.1**.
- Tagged `v0.13.1` and pushed to GitHub.

## [0.13.0] - 2026-06-25 - Surface sweep + experimental verbs

### Top-level promotion
- Eight subsystem modules (`minxg.twin`, `minxg.lens`, `minxg.lossless`,
  `minxg.self_evolution`, `minxg.polyglot`, `minxg.driver`, `minxg.cap`,
  `minxg.contracts`) are now reachable as top-level attributes
  (`import minxg; minxg.twin`) — same convention as the six math pillars.
  `from minxg.<x> import ...` continues to work. Added to `minxg/__all__`.

### Documentation cleanup
- Deleted the entire `docs/archive/` folder (10 files) including
  the obsolete multi-AI negotiation file `docs/archive/AGENTS.md`
  (formerly used to inject anti-loop directives into AI system prompts).
- README updates: dead link to phantom `docs/OPERATORS.md` removed;
  expired `# Successfully installed minxg-beta-0.10.0` snippet updated
  to 0.13.0; `v0.11.0` stale tag in the experimental surface section
  collapsed to a runtime-truth table; the `ga` ID-range claim
  `5000-5049` corrected to `5000-5046` (the actual registered range).
- DEVELOPER.md: new "v0.13.0 release notes" section before the historical
  v0.11.0 notes; §12 "Publishing checklist" updated to current numbers.

### New [EXPERIMENTAL] CLI verbs (0.13.0)
All five live behind `multiligua_cli/experimental.py` and broadcast an
`[EXPERIMENTAL] minxg <verb> — signature may change` banner. They are
exercised by `tests/test_experimental_cli.py` so a regression breaks CI.

- `minxg bench` — local perf snapshot of `lossless`, `driver`, `twin`,
  `polyglot`, `operators`, and experimental import path.
- `minxg replay <file>` — re-render a markdown chat log (output of
  `features.export_to_markdown`) back into the TUI-friendly stream.
- `minxg theme [name]` — get/set the active TUI theme
  (`dark` / `colorful` / `minimal`); state in `~/.minxg/theme.json`.
- `minxg safe-eval <expr>` — restricted expression evaluator. Allowed
  builtins: `abs`, `all`, `any`, `bool`, `dict`, `enumerate`, `float`,
  `int`, `len`, `list`, `max`, `min`, `pow`, `range`, `round`, `sorted`,
  `str`, `sum`, `tuple`, `zip`. No attribute access, no comprehensions,
  no lambda/import/class.
- `minxg ext-reload --all` — rescan extension sources without
  restarting the Python interpreter.

### CI / Tests
- `tests/test_experimental_cli.py` (NEW, 14 tests) covers every new
  verb plus the top-level-promotion contract for the eight subsystems.
- `tests/test_version_lock.py` (NEW, parametric) catches drift between
  `pyproject.toml`, `minxg/__init__.py`, `README.md`, and
  `CHANGELOG.md`.
- Bug fixes found during the surface sweep:
  - `multiligua_cli/wizard_ui.py` — when `readchar` is missing, the
    module now exposes `readchar = None` so test introspection paths
    stay defined (instead of `AttributeError`).
  - `tests/test_cap_extra.py::test_cli_cap_check_returns_zero_on_clean_tree_subprocess`
    — child interpreter now inherits `PYTHONPATH` so the unit-under-test
    script can `import minxg` in dev environments.

### Operator registry correctness
- The README's ID-range claims are now machine-checkable:
  `minxg.operators.OPERATOR_REGISTRY.total_operators` returns **376**
  (11 categories), `list_categories()` enumerates them, and the six
  mathematical pillars (`ga`/`cat`/`fiber`/`topo`/`chaos`/`infogeo`)
  contribute the documented **306 mathematical IDs**.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.12.5] - 2026-06-24 - Test suite expansion + Makefile pytest integration

### Testing
- **Makefile test target now runs pytest.** Replaced the broken C-only bridge path with `python -m pytest tests/ -q`, added `test-quick` (default, integration excluded) and `test-full` (all tests). `make test` is now the canonical way to run the suite and will fail on errors.
- **Added 217 new test cases across previously uncovered modules:**
  - `tests/test_cli_main.py` (15) — CLI entry-point surface (argparse subcommands, `--version`, `-v/--verbose`, `--list-extensions`, no-arg TUI dispatch, `minxg setup`/`help`/`model`/`api`/`key`/`lang`, unknown command).
  - `tests/test_cli_gateway.py` (12) — Gateway CLI verbs (`start --foreground`, `stop`, `status`, unknown-subcommand error), port/host overrides, API-key generation fallback.
  - `tests/test_cli_tui.py` (15) — TUI chat and interactive helpers (`print_banner`, `HAS_RICH` fallback, `colorize`, `_escape_markup`, `ensure_config` decorator, `_save_config` atomic write, `get_config_path`).
  - `tests/test_wizard_ui.py` (12) — `MinxgMenu` construction, `run()` with no-readchar numbered input, readchar arrow-key path, cancel via `q`/EOF/`KeyboardInterrupt`, description rendering.
  - `tests/test_i18n.py` (12) — `T()` key lookup, `set_lang`/`get_lang`, `LANGUAGES`/`LANG_CODES`/`LANG_NAMES` consistency, unknown-key fallback, unknown-lang behavior.
  - `tests/test_orchestrator.py` (9) — Orchestrator import, `start_api_server` coroutine signature, config merge shape, API-key generation fallback, env precedence.
  - `tests/test_agent_core.py` (11) — Agent reflection, capability, role, session imports; `ReflectionEngine` summarise; `AgentCapability` flag methods; session broadcast + message tracking.
  - `tests/test_queue_cache.py` (16) — `FifoQueue` FIFO order, `PriorityQueue` ordering, `LruCache` eviction, `TtlCache` expiry.
  - `tests/test_scheduler.py` (8) — Scheduler import, enqueue/dequeue round-trip, empty-queue drain, `start()`/`stop()` lifecycle with mocked sleep.
  - `tests/test_gateway_runner.py` (13) — Gateway runner import, runner instantiation, inference router import, `TaskGrader` grade levels, `WorkerRouter` legacy routes, `GatewayServer.initialize()` with mocked aiohttp deps.
  - `tests/test_tools_registry.py` (8) — Tool registry singleton, worker registration round-trip, unknown worker returns None, deregister, schema round-trip.
  - `tests/test_self_evolution_extra.py` (15) — `failure_tour` mutation injection, `field_forge` proposal count, `evolution_loop` phase transition happy path, twin engine comparison.
  - `tests/test_driver_extra.py` (11) — Engine instantiation, metric property, operator replacement/removal safety, phase transitions, state clone/merge.
  - `tests/test_lossless_extra.py` (10) — Codec round-trips, magic/truncation/version rejection, skeleton round-trip, BIE sphere embedding.
  - `tests/test_twin_extra.py` (8) — `python_to_rust` if/else/for/while, unsupported rejection, `rust_to_python` arithmetic/bool round-trips.
  - `tests/test_lens_extra.py` (7) — Glossary translation, unknown term passthrough, projector per-language rendering, English-word translation in Chinese context.
  - `tests/test_cap_extra.py` (9) — `scan_tree` path-order, sorted `what_provides`, balanced `check()`, `changes_since` diff, subprocess `minxg cap check`.
  - `tests/test_operators_extra.py` (6) — All 6 pillar operator sets present, total count ≥ 300, name lookup returns callable, legacy categories populated, idempotent registration.

### CI
- `make test` now produces a real pytest exit code (non-zero on failure), so CI shells no longer swallow test errors.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.12.4] - 2026-06-22 - MINXG Chat rewrite + flicker-free picker + safe print

### MINXG Chat rebuild
- **A proper REPL replaces the old "you > " stub.**
  `tui_chat()` now lives entirely in `multiligua_cli/tui_chat.py`
  and ships a polished three-region UI: a top status bar
  (`provider · model · host · depth/cost`), a scrolling conversation
  thread that streams tokens under `rich.live`, and a
  helper-rich bottom input box. The brand label inside the banner is
  **`MINXG Chat`** (formerly the ambiguous "chat CLI") — the change
  is documented in README §Tutorial A.
- **Brand refactor.** The hard-coded product name in the chat
  surface, `/help`, README, and DEVELOPER.md is consolidated under
  `tui_chat._BRAND = "MINXG Chat"`. Updating the brand now means
  changing one constant.
- **Streaming faithful to upstream events.**
  `_stream` consumes `text / thinking / tool_call / tool_result /
  done / error` events from `NexusOrchestrator.chat_stream` and
  renders tool calls as inline `→ name (Nms)` widgets with a
  yellow anti-loop warning line if the safety guard fires.

### In-place reconfiguration (no chat restart)
- **New slash commands**: `/setup`, `/provider [slug]`, `/model
  [name]`, `/url [URL]`, `/apikey [KEY]`, `/lang [code]`,
  `/history`. They hot-swap the orchestrator, save the config
  atomically (`tmp + os.replace`), and re-paint the status bar
  without dropping the session.
- **`/provider <slug>` is non-interactive** (omit the slug for the
  picker). `/model <name>` tries to fetch `GET /models` from the
  current provider; if the API is reachable, the picker shows the
  real list of available models. If the fetch fails, it falls back
  to the provider's `default_model` and accepts typed input.
- **`/setup` reruns the wizard with the existing config as
  defaults**, then re-renders the chat banner — no more "exit chat
  → `minxg setup` → re-enter chat" round-trip.
- **`/apikey` is masked** before being written to disk, the way
  the wizard has always done it. Naked key payloads no longer leak
  to log files.

### Bug fixes
- **`MinxgMenu` no longer flickers under Termux.** The old
  `_render` forked `clear` on every arrow-key press and wiped the
  whole scrollback; the new implementation paints in place using
  `\033[<n>A` (cursor up) + `\033[J` (erase to end of screen), so
  the chat scrollback stays intact and no full-screen flicker
  shows up under tmux/SSH/screen.
- **`print_error / print_success / print_info / print_warning /
  print_dim` no longer crash on user messages that contain
  brackets.** A new `_escape_markup` escapes `[` and `]` in
  inbound strings before handing them to rich, so URLs, exception
  messages and model names with brackets stop raising
  `rich.errors.MarkupError` inside the chat prompt.

### NUANCE alignment
- The new `_save_config` (atomic write) centralises every
  one-shot setter that previously hand-rolled `yaml.dump` —
  `minxg model <name>`, `minxg api <url>`, `minxg key <key>`,
  `minxg lang <code>` now share one error-handling path.
- All chat-side saves log a friendly `Config saved to ...` /
  `Save failed: <hint>` line so the user can see exactly which
  file was touched (and why) — instead of dumping a yaml
  traceback on top of a half-finished wizard panel.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.12.3] - 2026-06-22 - CLI polish + setup wizard UnboundLocalError fix

### Bug fix
- **`minxg setup` no longer raises `UnboundLocalError: cannot access local
  variable 'run_setup'`.** The wizard's full-run dispatcher in
  `multiligua_cli/main.py` was named `run_setup`, which shadowed the
  same-named import inside `main()` and made the symbol local —
  the very first invocation from the CLI now hit the classic
  local-before-assignment trap. The dispatcher is renamed to
  `cmd_setup`, the `@ensure_config` decorator is removed (wizards
  don't need to recursively invoke themselves), and the resulting
  duplicated banner is dropped because the wizard prints its own
  rich panel. `minxg model`, `minxg api`, `minxg key`, `minxg config`,
  and `minxg status` were already fine — only the `setup` path was
  exposed.

### CLI beautification
- **Quiet by default.** The `Loading tool modules...` and
  `Registered N tools from new system` INFO lines from
  `multiling/orchestrator.py` no longer print to stderr on every
  command. The logging root now starts at WARNING in interactive
  shells and is bumped to INFO only when `minxg -v` is passed
  (or `MINXG_LOG_LEVEL=DEBUG` is exported for diagnostics).
- **Banner shows the real version.** The header panel now reads
  `MINXG — Five-Pillar Worker Platform v0.12.3` (the
  `minxg.VERSION` constant is rendered live instead of relying on
  whichever snapshot was last edited into the banner template).
- **Setup wizard ribbon.** The wizard banner gets a `◆ tagline   vX.Y.Z`
  accent line and a `setup wizard` sub-line so the user knows what the
  screen is for the moment they enter `minxg setup`.
- **Step counter is correct.** `TOTAL_STEPS` is now `6` (was `5`), the
  duplicate `step 2 of 5` for the mode prompt is now `step 3 of 6`,
  the orphaned `step 7 of 5` for Browser Search is now `step 6 of 6`,
  and the dead-step `step 8 of 5` Summary banner has been removed in
  favour of a non-step gold "Review your configuration" panel.
  `setup_platforms` (and the now-redundant comment) is documented as
  a compatibility shim so future readers don't think it ran.
- **Wide-terminal-aware descriptions.** Menu descriptions used to be
  hard-truncated to 28 characters. They now size themselves between
  28 and 56 based on `shutil.get_terminal_size`, so a desktop user
  gets the full provider description while Termux users still keep a
  single-line layout.
- **Setup finishes with a celebration.** `_post_setup_hints` now prints
  a centred `✓ Setup complete` panel plus a two-column quick-reference
  grid (`minxg`, `minxg gateway start`, `minxg doctor`, …) so the
  first action after install is obvious.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.12.2] - 2026-06-21 - PyPI publication + release automation

### Published on PyPI
- `minxg-beta` is now installable directly from PyPI:
  `pip install minxg-beta`.
- Releases are fully automated via `.github/workflows/release.yml` —
  pushing a `v*.*.*` tag triggers Trusted Publishing (OIDC) for PyPI
  and creates a GitHub Release with the wheel + sdist attached.
  No PyPI API token is stored in the repository.

### Housekeeping
- README: top-of-file PyPI / Downloads / GitHub Release / License badges.
- README: replaced "PyPI publication is on the roadmap but not yet done"
  with a real `pip install minxg-beta` block and a `Releasing` section.
- pyproject: project `description` now mentions the PyPI name and
  install command so it surfaces on the PyPI page itself.
- PyPI metadata: removed retired `Topic :: Artificial Intelligence`
  classifier (PyPI no longer accepts it).

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> **Versioning policy (effective 2026-06-14):** MINXG is in pre-1.0
> development. Public releases start at **`0.10.0`**; the legacy
> `1.x` numbering on internal commits is retained in git history as
> a milestone but is **not** part of the public release graph.

## [0.12.0] - 2026-06-20 - Test coverage, experimental flags, install polish

Cold-start hardening plus a full-coverage test pass. The publish-
entry is `v0.12.0` (the prior `v0.11.0` tag was already on the
remote when this branch landed, so this release is being issued as
the next minor). The public API surface is unchanged. This tag
closes the gaps called out in the bug tracker (Pitfall 7, 31, 34,
38, 41) and back-fills test coverage so a regression that drops a
CLI command breaks CI.

### Added

* `tests/test_cli_commands.py` (25 tests, **was zero CLI coverage**).
  Exercises every subcommand, every global flag, and every
  `minxg ext <action>` verb; routes through
  `multiligua_cli.main.main(argv)` and writes to an isolated
  `config.yaml`.
* `tests/test_experimental_features.py` (6 tests). Verifies the
  `[EXPERIMENTAL]` labelling on `multiligua_cli.features` does not
  regress: the docstring names every experimental export,
  `list_experimental_exports()` is consistent, every
  `SilentFeatures` method emits a one-shot WARNING, and the known
  stubs (`check_updates` → `None`) keep their contract.
* AddressSanitizer harness (`tests/asan_harness.c`) +
  `build_asan/libminxg_asan.so`. Exercises every C entry point
  (arena reset cycles, slab alloc/free, ring push/pop, NCD pair,
  NCD matrix, sha256, url-encode/decode, tokenize) under
  `-fsanitize=address`. Local run returns **`rc=0`** — zero
  leaks, zero use-after-free, zero OOB.
* README command reference, tutorials (A-D), troubleshooting
  table, and experimental-surface section.

### Changed

* `install.sh` (5-step and 6-step ladder) — removed the automatic
  ADB and ROOT probe blocks. The script no longer reaches for
  `/system/bin/su`, `adb devices`, or `MAGISK_*`. ADB and ROOT ship
  as opt-in extensions only. The completion cheatsheet still
  advertises the opt-in slugs.
* `multiligua_cli/features.py` — top-of-file docstring now declares
  the module's experimental status, every public symbol carries an
  `[EXPERIMENTAL]` docstring tag, `SilentFeatures.__init__` and
  every method log a warn-once WARNING via the `features` logger,
  optional args are properly `Optional[str]` typed. New helper
  `list_experimental_exports()` returns the documented set.
* `.git rm --cached <build artifacts>` — five `c_core/*.o`, five
  `cpp_core/*.cpp.o`, and the legacy `libminxg_go.h` files were
  removed from git tracking (`.gitignore` already lists `*.o`,
  `*.so*`, `*.a`). The `foo.te_*` profile objects and three
  stray test driver `.c` files (`bmh_test.c`, `simple_test.c`,
  `debug_test.c`, `simple_bmh.c`) stayed registered; they're now
  ignored at the `.gitignore` level too.

### Memory safety audit (no P0, three P3 hardening notes)

* Static review with `grep`-based allocator/balancer over C and
  C++ source (5579 lines). Eight files showed alloc/free imbalance
  at first glance — on manual review each was a *balanced pair*
  where the free lives at a destroy-site (e.g. `arena_create`
  freeing on init failure) or is exposed to the caller as
  `cpp_free()` / `cpp_free_string_array()`. The interface is
  caller-owned throughout; no internal allocation leaks.
* Dynamic review via `libminxg_asan.so` + the harness: `rc=0`
  after 50 arena-reset cycles + 5×20 slab alloc/free cycles +
  ring-buffer overflow churn + NCD pair/matrix + sha256 + url
  paths. **Zero leaks, zero UAF, zero OOB.**
* Three hardening notes (P3, not blockers):
  * `cpp_wrapper.c:560` uses `strcpy(table[num_words].word, word)`
    in `cpp_word_frequency`. The input is bounded to `<64` chars
    (`len >= 64` is skipped earlier) so the write is in-bounds,
    but a `strncpy`/`memcpy` form is more obvious.
  * Multiple `codec-side` malloc callers do not NULL-check the
    return (e.g. `cpp_url_encode` line 191, `text_engine.c:660`,
    `minxg_evolve.c:341`). On a healthy system `malloc` always
    succeeds; on an OOM kill these would dereference `NULL`.
    Defence-in-depth: add `if (!out) return NULL;` early-returns.
  * `cpp_wrapper.c:crypt_*` paths do not check for `!in` when
    `in_len > 0` — easy fix, not currently triggered.

The above are tracked in the issue tracker; none of them are fixing
a present defect (the harness proves the happy path is clean).

### Footer

161 unit tests passing, 1 skipped (rustc / shell probe on
Android). The skipped test is environment-gated and not relevant
to the CLI.

## [0.11.0-pre] - 2026-06-19 - Opt-in extensions, native build fix, doctor command

Cold-start hardening release. No breaking-API changes; all the same
imports work in both directions. The big directional shift: built-in
extensions are now opt-in (no ADB/ROOT auto-detect at module load),
and the `multiligua_cli/doctor.py` self-check surface ships for the
first time. *Superseded by the canonical 0.11.0 entry above; kept
here as the pre-release notes.*

### Added - `minxg doctor`
  - `multiligua_cli/doctor.py` - new self-check command with an
    exit-code contract (0 OK, 1 fail, 2 warn). Reports on platform,
    binaries, minxg package surface, runtime config, extensions.
  - Plugged into argparse under `minxg doctor` so users have one
    answer for "is my install healthy?".

### Changed - Built-in extensions are opt-in (pitfall 31/34)
  - `extensions/__init__.py` and `extensions/loader.py` rewritten.
    The auto-detect ladder (ADB_AVAILABLE / ROOT_AVAILABLE drive the
    enable flag) is gone. Each built-in now ships with
    `EXTENSION_ENABLED = False`; opt-in is via
    `minxg ext add <slug>`, which writes
    `extensions/user/<slug>.state`.
  - `extensions/builtin/adb_ext/__init__.py`,
    `extensions/builtin/root_ext/__init__.py`,
    `extensions/builtin/files_ext/__init__.py` rewritten in English
    (no Chinese in user-facing strings) with probe-on-call helpers
    (`_adb_available()`, `_root_available()`) instead of
    probe-at-import.
  - `extensions/__init__.py` exports `set_extension_enabled` to back
    the opt-in surface. The `import_hermes_skill` /
    `import_claude_skill` / `import_codex_tool` / `run_ext_import`
    stubs (which referenced an undefined `wrapper_code`) are removed.

### Fixed - cpp_core build link error (real bug)
  - `cpp_core/CMakeLists.txt` built `libminxg_core.so` from
    `cpp_wrapper.c` alone, but the wrapper references
    `minxg_slugify`, `minxg_truncate`, `minxg_word_freq_hash` from
    `c_core/text_engine.c`. The resulting shared library crashed
    every `ctypes.CDLL` call with `cannot locate symbol
    "minxg_slugify"` on Termux/Py3.13.
  - CMakeLists now also links `c_core/text_engine.c` into
    `minxg_core`. Verified at runtime: `core_native.sha256` returns
    correct hashes.
  - `install.sh` no longer claims ADB / ROOT extensions
    "auto-enabled"; users get a plain `minxg ext add <slug>` hint.

### Changed - install.sh
  - Stripped 43 `[CN]` placeholder markers that were left behind from
    an in-progress Chinese-to-English conversion.
  - Removed the auto-enable messaging for ADB / ROOT extensions.
  - Brand line `MINXG v1.0.0` -> `MINXG v0.11.0`.
  - Extension summary block now reports `[on]` / `[off]` based on
    the runtime `enabled` flag, not the old `INACTIVE` substring
    regex.

### Changed - py_workers alias
  - The compat stub now exposes pillar aliases via its own
    `__getattr__`. `py_workers.scalar`, `py_workers.io`,
    `py_workers.<math>` all resolve.
  - Version fallback `getattr(_minxg, 'VERSION', '1.1.0')` ->
    `'0.11.0'`.

### Misc - Housekeeping
  - Bumped `minxg.VERSION` and `pyproject.toml:version` to `0.11.0`.
    `config/minxg.yaml:project.version` synced.
  - Replaced the orphan `multiligua_cli.main:doctor` reference with
    the now-existing `multiligua_cli.doctor.run_doctor`.
  - `multiligua_cli/main.py`: collapsed 19 triple-blank-line blocks
    the partner's draft left behind.
  - `tests/test_extensions.py`: rewrote TestADBRootDetection ->
    TestBuiltinOptIn to assert opt-in (no ADB_AVAILABLE at module
    load, English-only descriptions, state-file persistence works).

### Verification
- 130 tests pass, 1 skipped (rustc absent in Termux sandbox).
- `minxg --version` reports `0.11.0`.
- `bash install.sh --help` exits 0 with the post-install cheatsheet.
- `py_workers.scalar` and `py_workers.ga` resolve via the alias.

## [Unreleased] — Documentation & loader audit

Independent code audit (2026-06-19) found four marketing-vs-reality
gaps and one real loader bug. All five are patched in this entry;
no public version bump (still `0.10.0`).

### Fixed — loader
- **`minxg.five_pillars.scalar.core_native._find_lib()` was searching
  the wrong tree root.** It walked from `minxg/five_pillars/` upward
  only one level, so `cpp_core/build/libminxg_core.so` (the library
  that ships in the repo) was never reached. The Android-Termux
  hardening branch (`shutil.copy2` into
  `/data/data/com.termux/files/usr/lib/`) was therefore dead code on
  the platforms it was written for. The detector now walks up to the
  project root via `pyproject.toml`, checks
  `cpp_core/build/`, `cpp_core/`, and `build/` in that order, and
  still leaves the Android copy-to-lib step intact.
- **Honest fallback message.** Old code's "fall back to
  `minxg_core.so`" returned the bare name when nothing matched,
  leading `ctypes.CDLL` to emit a misleading `dlopen failed` instead
  of a clear "native library not found, run with PURE PYTHON". The
  fallback is now an explicit `OSError` with the actual discovery
  outcome.

### Changed — README / pyproject (marketing accuracy)
- **`pyproject.toml` description.** "376+ math operators" → "306
  mathematical operators (376 total across 11 categories)". `376`
  is real (it's the full `OPERATOR_REGISTRY.total_operators`); `306`
  is the subset exposed as `minxg.TOTAL_MATHEMATICAL_OPERATORS` (the
  sum of the six mathematical pillars). Old wording treated `376`
  as `math`, which is off by 70 and made it sound like 306 of 376
  were missing.
- **`README.md` Mathematical pillars section.** "300+ stable
  operator IDs on import" → "**306** mathematical operator IDs in
  stable ranges on import (376 total across all 11 categories;
  see `OPERATORS.md`)".
- **`README.md` lossless block.** "For lossless compression" →
  "For the lossless BIE round-trip codec" with an explicit caveat
  that the encoded form is typically *larger* than the input on
  real-world data. The bullet under "Self-developed subsystems"
  was rewritten from "BIE-geometry lossless compression" to
  "BIE-geometry byte-identical round-trip" with the same caveat.
  The codec still round-trips byte-exactly (CRC-32 verified); it
  just isn't a competitor to zstd.

### Changed — README (boundary honesty for two subsystems)
- **`minxg.polyglot` description.** "Multi-language AST normaliser"
  → "Multi-language source-to-graph normaliser". Adds explicit
  boundary: Python uses real `ast`; Rust / JavaScript / Go / shell
  are regex-based heuristics — useful for code-shape recognition,
  not a compiler front-end.
- **`README.md` tagline.** "multi-language polyglot, capability
  registry" → no change required (it already names both subsystems
  accurately at the package level). The "corpus" claim in this
  release's subsubsystem remained uncorrected in `minxg.cap` itself;
  cap-tagged source files currently number 7 (3 of which are
  inside `minxg/cap/`). Adoption is voluntary. Reader who wants a
  full corpus can run `python -m minxg.cap list` for the live list.

### Changed — config
- **`config/minxg.yaml` `project.version`.** "0.0.1a" → "0.10.0",
  matching `minxg.VERSION`. `minxg.get("project.version")` now
  returns the same number as `python -c "import minxg; print(minxg.VERSION)"`
  instead of the prior legacy mismatch.
- **`config/minxg.yaml` `project.description`.** Updated to match
  the same one-line summary in `pyproject.toml` and the README.

### Verification
- 130 tests pass + 1 skipped, ~1.5 s on Termux × Python 3.13.
- `python -c "import minxg; print(minxg.VERSION, minxg.TOTAL_MATHEMATICAL_OPERATORS)"`
  → `0.10.0 306`.
- `python -m minxg.cap.list` → 11 capabilities from 7 tagged files.

### Notes
- **`minxg.cap` corpus is small but honest.** README's reference to
  "capability registry" is accurate; the prior "Corpus-based" branding
  survives in CHANGELOG history but was removed from the README-by-
  bullet in this entry. The scanner, manifest, and CI hooks are all
  present and exercised by `tests/test_cap.py`; widening the corpus
  is opt-in (add `minxg.cap.provides:` tags to a module's top
  docstring).

### Further (same Unreleased) — config-truth & ID-range sync
- **`config/minxg.yaml` `self_evolution.algorithms: 10` → `components: 4`.**
  The repository ships exactly four cooperating pieces
  (`failure_tour.py`, `field_forge.py`, `twin.py`, `loop.py`). The
  old `algorithms: 10` was a marketing number with no backing code.
- **`config/minxg.yaml` `features.{hot_reload, anti_loop_guard,
  tidal_lock}` flipped to `false`.** README and CHANGELOG history
  have described each as removed / unimplemented since v1.1.x, but
  the YAML was advertising them as `true`. Truthful defaults now match
  the documented reality.
- **`config/minxg.yaml` dropped `self_evolution.compression: zstd-level-3`.**
  No code path under `minxg/self_evolution/` reads this value.
- **Pillar ID ranges in README + DEVELOPER.md corrected** from the
  outdated `5000–5499` / `4000–4499` / etc. (which reserved ~100 IDs
  per pillar that were never registered) to the actual ranges
  observed in `OPERATOR_REGISTRY._categories` — see YAML
  `operators.categories.*.id_range` for the canonical numbers.
- **Top-level README tagline softened** from "covering the full
  operator surface area" to a non-promissory phrasing. Also added a
  paragraph explaining the implicit pure-Python fallback when the
  native loader cannot find or dlopen a `.so`.
- **DEVELOPER.md §11 "Termux linker namespace" entry now lists the
  exact discovery order** (`cpp_core/build/` → `cpp_core/` → `build/`)
  and the explicit-OSError contract, so the next maintainer doesn't
  waste a session re-discovering what `core_native._find_lib` does.


This release supersedes both the original 0.10.0 snapshot and the
0.11.0 hot-fix re-versioning. Source-of-truth tag is **v0.10.0**.

### Fixed
- **Cold-start cryptography crash.** `multiling/ipc_server.py` no
  longer imports `cryptography` at module level. The dependency is
  lazy-loaded inside `_generate_ssl_cert()` and only when TLS is
  requested. Fixes `minxg tools` and `minxg open` failing on
  Termux × Python 3.13 (`cannot locate symbol "PyBaseObject_Type"`).
- **`ChatLogger._buffer` initialised in `__init__`.** `minxg files`,
  `minxg adb`, `minxg root`, and the TUI default (`minxg` with no
  args) used to flake with `AttributeError: '_buffer'` on first use.
- **`MinxgMenu.run()` non-readchar branch.** Clean fallback to
  numbered input with a `q`-to-quit exit when `readchar` is not
  available — no broken `NameError: choice` mid-flow.
- **Hardcoded version literals.** `multiligua_cli/utils.py`,
  `setup.py`, and `wizard_ui.py` no longer leak `"1.0.0"` while
  `minxg.VERSION` is on a different number. All consumer-facing
  labels now read `minxg.VERSION` via guarded import.
- **`multiligua_cli/i18n.py` fallback.** A built-in `_DEFAULTS`
  English dictionary ships inside the module, so a missing
  `i18n_data/en.json` no longer surfaces raw keys (e.g. `cmd_minxg`)
  in `minxg help` and the cheatsheet.
- **`multiligua_cli/providers.py` registry.** 32 AI providers
  (qwen, zhipu, moonshot, baichuan, stepfun, doubao, yi, spark,
  minimax, custom, local, …) all carry `name`, `emoji`, and
  `description` keys. The setup wizard no longer crashes with
  `KeyError: 'emoji'` when picking an AI provider.
- **`multiligua_cli/extensions/tui.py quick_list()`** constructs
  its Rich `Table` before iterating — previously referenced an
  unbound `table` name and crashed on every `minxg ext list`.

### Build / install hygiene
- Removed legacy editable-install leftovers from
  `/data/data/com.termux/files/usr/lib/python3.13/site-packages`
  (`__editable__.minxg-0.0.1a0.pth`, `multiling-3.4.0.dist-info`,
  `__editable___minxg_0_0_1a0_finder.py`, …) that were shadowing
  the live install and pointing at a stale `/storage/emulated/0/multiling/`
  working tree. Reinstall is clean via `pip install -e .`.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [0.11.0] — Re-versioning hot-fix (+0.01)  *[superseded by 0.10.0 above]*

### Changed
- **Re-versioned** `0.10.0` → `0.11.0`. No code changes; this is a
  marker commit to increment the public number on top of the
  original 0.10.0 snapshot, per project policy.
- `minxg.VERSION`, `pyproject.toml`, README all reflect `0.11.0`.
- CHANGELOG prepended with this entry; `0.10.0` section retained
  below as the source-of-truth snapshot for that tag.
- **Note:** The v0.11.0 GitHub release was deleted as part of the
  v0.10.0 re-release; the underlying commit history is preserved.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [0.10.0] — Corpus-based Capability Registry (first 0.x public release)

### Added
- `minxg.cap` — Corpus-based Capability Registry. Scans every Cell's
  `Capability` declarations across the contracts registry and exposes
  a single, queryable index (`cap lookup`, `cap info`, `cap diff`,
  `cap tree`, `cap regen`, `cap ci`). Backed by a deterministic
  manifest (`manifest.json`) keyed by Cell identity + capability
  signature, so two warehouse clones can be diff-ed byte-stable.
  Runs as a CLI (`python -m minxg.cap`) and as a normative gate in
  CI (`tests/test_cap.py`).
- First-time release-automation path: `git tag -a v0.10.0` →
  `gh release create v0.10.0 --target main`.

### Changed
- **Re-versioned:** `minxg.VERSION`, `pyproject.toml`, README are
  now `0.10.0`. Changelog history above `0.10.0` is preserved under
  the legacy section for trace-ability of internal milestones
  (v0.0.1a → v0.0.2-audit → v1.1.0 → v1.2.0 → v1.3.0-internal).
- `minxg/__init__.py` re-exports the `cap` submodule under a
  guarded import so `import minxg.cap` keeps working.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [1.3.0-internal] — Corpus-based Capability Registry (legacy numbering)

> Internal milestone — superseded by **0.10.0** as the first public
> release on 2026-06-14. The commit graph is preserved; the public
> tag was removed (only the GitHub-protected `v1.3.0` tag object
> remains in history as a reference point). Do **not** depend on this
> version externally.

### Added
- `minxg.cap` — Corpus-based Capability Registry. Scans every Cell's
  `Capability` declarations across the contracts registry and exposes
  a single, queryable index (`cap lookup`, `cap info`, `cap diff`,
  `cap tree`, `cap regen`, `cap ci`). Backed by a deterministic
  manifest (`manifest.json`) keyed by Cell identity + capability
  signature, so two warehouse clones can be diff-ed byte-stable.
  Runs as a CLI (`python -m minxg.cap`) and as a normative gate in
  CI (`tests/test_cap.py`).
- Tests for the cap subsystem: 16 tests, all passing.

### Changed
- `minxg.VERSION` is now `"1.3.0"`.
- `pyproject.toml` `version = "1.3.0"`.
- `minxg/__init__.py` now re-exports the `cap` submodule under a
  guarded import so `import minxg.cap` continues to work.

### Tests
- 130 passed (+1 skipped, no rustc on Termux), ~3 s

## [1.2.0] — Self-developed subsystems

### Added
- `minxg.contracts` — Cell / Port / Registry / Lifecycle framework.
  Cells advertise capabilities through a `CellMeta` metaclass and are
  registered once into a `Registry` that other Cells consult by
  capability name. Editing one Cell never touches the others.
- `minxg.driver` — Temporal Operator-Field driver engine. Operators
  are pure `State → State` mappings; the engine advances time with
  explicit Euler integration and adaptive sub-stepping on drift.
  Five phases (`ready`, `stepping`, `paused`, `halted`, `faulted`)
  exposed through `engine.on_phase(prev, new)` hooks.
- `minxg.self_evolution` — closed-loop self-improvement. `FailureTour`
  records engine failures; `FieldForge` queries the contracts
  registry for capable Cells; `TwinEngine` validates a swap on a
  shadow copy of the live engine; `EvolutionLoop.cycle()` commits
  the swap on twin-accept.
- `minxg.polyglot` — multi-language AST normaliser. Reduces Python /
  Rust / JavaScript / Go / shell to a single `OperatorGraph` shape
  with topological-order support. Pure Python; Rust/JS/Go/shell
  use regex heuristics.
- `minxg.lossless` — BIE-geometry lossless compression. Each byte
  becomes a unit-sphere point; byte-to-byte transitions become
  blades; the curvature skeleton is what gets stored, with a
  CRC-32 trailer guaranteeing byte-identical reconstruction.
- `minxg.twin` — Python ↔ Rust RTL emitter. `python_to_rust` covers
  function definitions, if / elif / else, while, for-range,
  augmented assignments, all standard expressions. `rust_to_python`
  reverses. Unsupported constructs raise `UnsupportedTwinOp`.
- `minxg.lens` — reverse docstring export. Bundled 14-entry
  glossary (operator / driver / bridge / registry / cell / port /
  field / state / drift / blade / curvature / worker / twin /
  evolution) maps EN → ZH / ZH-TW / JA / KO. Lens renders every
  section in every language, with a `GLOSSARY.md` summary table.

### Changed
- `minxg.VERSION` is now `"1.2.0"`.
- `pyproject.toml` `version = "1.2.0"`, license author "MINXG Authors".
- New top-level constants exported from `minxg.__init__`:
  `POLYGLOT_LANGUAGES`, `LOSSLESS_MAGIC`, `LOSSLESS_VERSION`,
  `TWIN_ERROR`, `SELF_EVOLUTION_PHASES`, `LENS_LANGUAGES`,
  `DRIVER_PHASES`, `DRIVER_DEFAULT_MAX_SUBDIVISIONS`.

### Tests
- 114 passed (+1 skipped, no rustc on Termux), ~2 s

## [1.1.0] — Five-pillar layout + contracts + driver + hot-reload removed

### Added
- `minxg/five_pillars/{scalar, aggregate, io, dispatch, transform}`
  layout — flat worker files moved into five orthogonal planes.
  Each pillar only depends on `minxg.base`; cross-pillar imports are
  fully qualified.
- `minxg/five_pillars/` re-exports the public surface so
  `from minxg import FsIoWorker` still works.

### Removed
- GitHub hot-reload subsystem. `multiligua_cli/hot_reload.py`,
  the `update` subcommand, the `/update` TUI shortcut,
  `setup_hot_reload`'s repo/branch prompts are gone. Use
  `pip install --upgrade minxg-beta` instead. See
  `docs/ARCHITECTURE.md` § "Self-evolution loop" for the rationale.

### Changed
- `minxg.driver` previously existed as the engine scaffold;
  promoted to a fully-implemented subsystem in v1.2.0.
- `py_workers/` is now a thin alias package with `__getattr__`
  pointing flat module names at `minxg.five_pillars.<p>.<x>`.

## [0.0.2-audit] — Repo hygiene & CI hardening

### Added

- `LICENSE` at repo root (MIT, matches `pyproject.toml`)
- `.env.example` template (real `.env` is git-ignored and chmod-locked)
- `.github/workflows/ci.yml` now asserts `OPERATOR_REGISTRY.total_operators == 376` and runs a separate `ruff` job
- `OPERATORS.md`: "How we count" — exact count is CI-enforced, not hand-edited
- `OPERATORS.md`: "Why these six pillars" — diff against functional taxonomy
- `ARCHITECTURE.md` § 5 rewritten with `c_core/` ↔ `cpp_core/` ↔ `go_core/` boundary policy and Termux/CDLLCID idiom
- `_legacy/README.md` — explains the legacy vault, sets a review cadence

### Fixed

- 43 source files still declared `py_workers/...` in their docstring banners after the rename → renamed to `minxg/...` (compat alias preserved)
- `minxg/ga/operators_ga.py` ID-range comment said `3500-4499`; actually registers at `5000-5049` → comment now matches
- README badge linking to `opensource.org/licenses/MIT` (generic) → linked to repo's own `LICENSE`
- `.gitignore` extended to suppress `_legacy/` and `.test_entropic/` from GitHub browsing

### Hygiene

- Removed stale `minxg.egg-info/` and `multiling.egg-info/`
- Real `.env` chmod-locked (`444`) to prevent accidental overwrite

## [0.0.2] — Architecture overhaul & documentation upgrade

### Changed — package renamed

- `py_workers/` renamed to **`minxg/`** (single canonical import)
- `py_workers/` retained as a backward-compat alias
- `pyproject.toml` `name = "minxg"`
- All cross-package imports updated
- No breaking change for users: `import py_workers` still works

### Added — centralized configuration

- `config/minxg.yaml` is the single source of truth for runtime config
  (project metadata, operator counts, pillar definitions, paths, features)
- `minxg.get(key)` reads config via dot-path (e.g. `minxg.get("project.version")`)

### Changed — documentation reorganization

- `docs/` directory **removed** (was redundant with project root)
- All HTML files **removed** (we use Markdown only)
- New root-level documents (each available in 5 languages where applicable):
  - `PROJECT_INDEX.md` — one-page project map
  - `ARCHITECTURE.md` — full system architecture
  - `INSTALL.md` — installation everywhere
  - `QUICKSTART.md` — 5-minute tour
  - `OPERATORS.md` — all 376 operators
  - `EXTENSIONS.md` — build your own
  - `SELF_EVOLUTION.md` — the 10 algorithms
  - `TIDAL_LOCK.md` — C acceleration
- All pillar READMEs (`.md`, `.zh.md`, `.ja.md`, `.ko.md`) live **next to
  the code** (in `minxg/<pillar>/`) — finding pillar docs no longer
  requires searching the whole repo
- All `5 root-level READMEs` (en / zh / zh-TW / ja / ko)

### Changed — comment hygiene

- All inline comments and decorative docstrings removed from
  `minxg/` Python files (the code reads itself)
- Public API docstrings retained

### Fixed

- Cloud tools `env_template` f-string regression caused by overzealous
  comment stripping — fixed

## [0.0.1a] — Initial alpha with 6 mathematical pillars

### Added

- 6 mathematical pillars (306 new operators) on top of original 70:
  - **GA** Geometric Algebra (Clifford) — 47 operators
  - **CAT** Category Theory — 79 operators
  - **IG** Information Geometry — 51 operators
  - **TOPO** Algebraic Topology — 53 operators
  - **CHAOS** Dynamical Systems & Chaos — 23 operators
  - **FIBER** Fiber Bundles — 53 operators
- Pure-Python implementations (no numpy)
- Original 10 self-evolution algorithms
- Tidal Lock C acceleration (11 functions)
- 50+ workers (FS, network, state, crypto, ML, system, process)
- Multi-platform support (Termux, Linux, macOS, iOS, IoT)

### Total: 376 operators, 11 categories, 6 mathematical pillars
