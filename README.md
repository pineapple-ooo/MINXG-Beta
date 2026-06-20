# MINXG

A modular AI worker platform with a built-in chat CLI, an OpenAI-compatible
v1 gateway, opt-in extensions (ADB / ROOT / files), and a self-developed
temporal driver engine — all in one Python package.

`pip install minxg-beta` drops you on Termux, Linux, macOS, and WSL
with a single `minxg` binary on `$PATH`. Workers are split across
five orthogonal operator planes (io, aggregate, scalar, transform,
dispatch), so editing one module never forces a full rebuild.
Pure Python — no compiled step required to install or run.

- This is the **v0.12.0** release. (The commit landed on `main` after
  the prior `v0.11.0` had already been tagged on the remote; the
  GitHub ref-creation rule blocks us from re-creating `v0.11.0`,
  so this is published as `v0.12.0`.) It ships cold-start
  hardening plus a polished setup wizard:

- `minxg` (no subcommand) now asks: chat CLI, start API gateway, or
  run the setup wizard — instead of dropping straight into a TUI
  shell.
- Setup wizard supports the OpenAI-standard `reasoning_effort` knob
  (`xhigh` / `high` / `medium` / `low` / `minimal` / `none`) with
  per-provider support maps (OpenAI supports all five, Anthropic
  three, Gemini five, DeepSeek / Doubao / xAI four, etc.).
- Wizard menus strictly fit a single line per option — descriptions
  are truncated to 28 chars so Termux 80-col screens stop spilling
  one option across two terminal rows.
- Built-in extensions (`minxg-adb`, `minxg-root`, `minxg-files`)
  ship opted-OUT. Users enable with `minxg ext add <slug>`. No
  silent auto-attaching to whatever API happens to be on PATH.
- `cpp_core/CMakeLists.txt` link error fixed: `libminxg_core.so`
  no longer crashes on `dlopen` with
  `cannot locate symbol "minxg_slugify"` on Termux + Py3.13.
- `minxg model`: the AI provider registry was missing `name`,
  `emoji`, and `description` for the second half of the providers,
  crashing the setup wizard with `KeyError: 'emoji'`. All 32
  providers are now normalised.
- `cpp_core/src/json_stringify.cpp` adds a flat C ABI over the C++
  `json_fast` parser (re-parses per call so no `std::variant`
  crosses the boundary on aarch64 Android, returns malloc'd buffers
  freed via `cpp_json_free`). Exposed to Python through
  `native_integration.CPPJsonNative` with a `JsonBuffer` lifetime
  wrapper that holds the raw `c_void_p` pointer (the heap-corruption
  footgun from using `c_char_p` is now memoralised at the top of the
  class).
- `java_core/` ships a polyglot JVM-side daemon — line-oriented JSON
  RPC on TCP, in-memory vector engine, knowledge graph, session
  memory, persistent log — built with `javac` (no Maven/Gradle
  required). Intended for users who already run a JVM and want a
  hostable backend independent of the Python driver. Source-only;
  build artefacts (`build/`, `*.jar`) stay out of git via the
  existing `.gitignore`.
- Test suite now **exercises every CLI command** so a regression
  that removes or renames a subcommand breaks CI (`tests/test_cli_commands.py`).
  130 → 161 unit tests.  AddressSanitizer harness (`tests/asan_harness.c`,
  `build_asan/libminxg_asan.so`) verifies zero leak / zero use-after-free
  across every C API; the `.so` files in repo root and `c_core/*.o`
  have been removed from git tracking (still ignored by `.gitignore`).
- Install script no longer probes for `adb` / `su`. ADB & ROOT ship
  as opt-in extensions (`minxg ext add minxg-adb`,
  `minxg ext add minxg-root`) so the install path is identical
  on dev workstations and locked-down CI.

## Install

The Python package's distribution name is **`minxg-beta`** and the
top-level import is **`minxg`**.

### One-liner (any platform)

```bash
curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash
```

That single command:
- detects your platform (Termux / Linux / macOS / WSL),
- clones the full repo to `~/.minxg-src`,
- pip-installs everything in editable mode so the `minxg` console
  script lands on `$PATH`,
- compiles the optional C extensions if a compiler is present,
- prints a status table at the end.

Variants:

```bash
# custom clone dir
MINXG_DIR=/opt/minxg curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash

# explicit repo URL (when forking)
REPO_URL=https://github.com/you/minxg.git curl -fsSL https://raw.githubusercontent.com/Disability-Human/MINXG-Beta/main/install.sh | bash
```

### Local clone (developer)

```bash
git clone https://github.com/<owner>/minxg.git
cd minxg
bash install.sh          # picks up the existing clone, skips the git step

After install:

```python
import minxg
print(minxg.VERSION)         # "0.10.0"
print(minxg.detect_platform())
```

Verified end-to-end on Termux/Android (`Python 3.13`) and Linux:
```bash
$ pip install -e .
Successfully installed minxg-beta-0.10.0

$ python3 -c "import minxg; print(minxg.VERSION, len(minxg.__all__), 'workers;', minxg.TOTAL_MATHEMATICAL_OPERATORS, 'math ops')"
0.10.0 55 workers; 306 math ops
```

**PyPI publication is on the roadmap but not yet done.** Until the
package shows up on PyPI under the `minxg-beta` name, the source-
tree mode above is the supported install path.

The codebase has no compiled dependencies on install; everything in
`minxg/five_pillars/`, `minxg/driver/`, `minxg/contracts/`,
`minxg/self_evolution/`, `minxg/polyglot/`, `minxg/lossless/`,
`minxg/twin/`, `minxg/lens/`, and the six mathematical pillars is
pure Python. Fall-back to pure Python is implicit: when no native
library is found or `dlopen` fails, the Python implementation is
used. The Termux/Android pipeline runs end-to-end via the lazy
loader for `cryptography` and the project-root-anchored
`core_native._find_lib` walker.

## Quick start

```python
import minxg

print(minxg.VERSION)
print(minxg.detect_platform())

fs = minxg.FsIoWorker()
result = await fs.list_directory(path="/tmp")
```

For the driver engine (substitute for a task graph):

```python
from minxg.driver import State, DriverEngine, smoothing_field

state = State(payload={"x": 0.0, "v": 1.0})
engine = DriverEngine([smoothing_field(rate=0.4)])
end, report = engine.run(state, n_steps=24)
```

For the lossless BIE round-trip codec:

```python
from minxg.lossless import LosslessCodec

codec = LosslessCodec()
result = codec.compress(b"some payload")     # wraps an MINSKE blob + CRC-32
back = codec.decompress(result.payload)
assert back == b"some payload"               # byte-identical, not size-optimised
```

This is a BIE (blade-decomposition) *byte-identical round-trip* — useful
as a structured representation of byte streams, not a competitor to
zstd/gzip. On random or low-redundancy inputs the encoded form is
larger than the source.

## Five pillars

The 55 worker classes are organised along five orthogonal planes:

```
minxg.five_pillars.scalar       pure compute        math / datetime / text / color
minxg.five_pillars.aggregate    encoders            crypto / encoding / ml / templates
minxg.five_pillars.io           external surfaces   fs / net / media / web / cloud
minxg.five_pillars.dispatch     execution / limits  system / sh / adb / root
minxg.five_pillars.transform    state and events    persistence / rules / ai
```

Edit one worker, nothing else moves.

## Self-developed subsystems

* `minxg.driver` — Temporal Operator-Field driver engine. Operators
  are pure functions on a shared state manifold; advancing one step
  is explicit Euler integration with adaptive sub-stepping on drift.
* `minxg.contracts` — Operator-Cell registry. Each Cell advertises
  capabilities; replacing one Cell never touches the others.
* `minxg.self_evolution` — Closed-loop self-improvement. A bouncer
  records engine failures, a forge hunts capable Cells from the
  contracts registry, a twin engine validates a swap is drift-safe
  before committing.
* `minxg.polyglot` — Multi-language source-to-graph normaliser.
  Python uses real `ast`; Rust / JavaScript / Go / shell use
  regex-based structural heuristics (not full parsers). All five
  reduce to a single `OperatorGraph` with topological-order
  edges — good enough for code-shape recognition, not a compiler
  front-end.
* `minxg.lossless` — BIE-geometry byte-identical round-trip. Every
  byte becomes a unit-sphere point; transitions between bytes
  become blades; the curvature skeleton is what gets stored, with
  a CRC-32 trailer guaranteeing byte-identical reconstruction.
  Structurally interesting; output is typically *larger* than the
  input on real-world data.
* `minxg.twin` — Python ↔ Rust RTL compiler. Source-equivalent twin
  emitters cover if/elif/else, while/for-range, augmented assignments,
  binop/compare expressions.
* `minxg.lens` — Reverse-docstring exporter. Render any one
  description into EN / ZH / ZH-TW / JA / KO doc files + a glossary.

## Mathematical pillars

Six categorical libraries ship with the package and register
**306 mathematical operator IDs** in 6 non-overlapping ranges on
import (376 operators total across all 11 categories; see
`OPERATORS.md`):

```
minxg.ga         5000-5049   geometric algebra       (47 ids)
minxg.cat        4000-4078   category theory         (79 ids)
minxg.infogeo    7000-7050   information geometry    (51 ids)
minxg.topo       8000-8052   algebraic topology      (53 ids)
minxg.chaos      8500-8522   dynamical systems       (23 ids)
minxg.fiber      6000-6052   fiber bundles           (53 ids)
```

## Documentation

* `DEVELOPER.md` — full developer reference, one file
* `docs/ARCHITECTURE.md` — architecture diagrams and rationale
* `docs/DRIVER.md` — driver engine API and examples
* `docs/PILLARS.md` — one section per mathematical pillar

## Command reference

The shipped CLI surface is small on purpose. Every subcommand and
flag below is exercised by `tests/test_cli_commands.py`; if you
rename or remove one of them, CI will fail.

### Top-level commands

| command            | what it does                                                           |
|--------------------|------------------------------------------------------------------------|
| `minxg`            | Cold-start picker: chat CLI, OpenAI-compatible gateway, or setup.      |
| `minxg setup`      | Interactive setup wizard (run once; repeatable).                       |
| `minxg config`     | Print current configuration (provider/model/key/etc.).                 |
| `minxg status`     | Print system status (Python / platform / version).                     |
| `minxg tools`      | List available toolsets and tool names.                                |
| `minxg help`       | Pretty command cheatsheet.                                             |
| `minxg model`      | Without arg: re-launch setup. With `<NAME>`: one-shot set the model.   |
| `minxg api <URL>`  | One-shot set the API base URL.                                         |
| `minxg key <KEY>`  | One-shot set the API key.                                              |
| `minxg lang [LC]`  | Switch display language. Without arg: picker. With `<LC>`: one-shot.   |
| `minxg gateway`    | `start` / `stop` / `status` (default `status` when omitted).           |
| `minxg doctor`     | Twelve-row self-check; exit 0/1/2 = clean/fail/warn.                   |
| `minxg ext <a>...` | Manage extensions: `list`, `available`, `add`, `remove`, `info`,       |
|                    | `enable`, `disable`. Run `minxg ext --help` for the full list.         |

### Global flags

| flag                | effect                                                         |
|---------------------|----------------------------------------------------------------|
| `--version`         | Print `multiligua_cli.__version__` and exit.                   |
| `-h`, `--help`      | argparse-style help.                                           |
| `-v`, `--verbose`   | Raise logging level to DEBUG.                                  |
| `--list-extensions` | Print every registered extension (name, source, priority, desc).|

### Extension subcommands

```text
minxg ext list                 # show active extensions
minxg ext available            # show built-in opt-in slugs
minxg ext info <slug>          # describe a slug
minxg ext add <slug|path>      # install built-in or local package
minxg ext remove <name>        # remove an installed extension
minxg ext enable <name>        # enable without re-installing
minxg ext disable <name>       # disable without removing
```

The three built-in opt-in slugs are `minxg-adb`, `minxg-root`,
`minxg-files`. They install off-PATH tools; none of them silently
auto-attach to whatever binary happens to exist when `minxg` starts.

### Examples

```bash
# fresh install with public config
minxg setup
minxg config

# one-shots — no wizard
minxg model gpt-4o
minxg api https://api.openai.com/v1
minxg key $OPENAI_API_KEY

# start the gateway in the foreground
minxg gateway start --foreground

# discover extensions
minxg ext available
minxg ext info minxg-adb
minxg ext add minxg-adb          # opt-in tool: not run during install
```

## Tutorials

### A. First conversation in 60 seconds

```bash
minxg setup               # one wizard, picks provider + key
minxg config              # confirm
minxg                     # TUI chat
```

If your provider supports `reasoning_effort`, the wizard step
offers the OpenAI-standard ladder
`xhigh > high > medium > low > minimal > none`. Pick a value, then
the wizard persists it under `ai.reasoning_effort` in `config.yaml`.

### B. Use `minxg` as an OpenAI-compatible backend for any client

Point your favourite client at the gateway:

```bash
minxg gateway start              # listens on 127.0.0.1:18080
#       -d / --detach runs in background; --foreground stays attached

$EDITOR config.yaml             # add base_url & api_key under ai:
minxg gateway status            # shows /v1/models dump
```

```bash
curl http://127.0.0.1:18080/v1/chat/completions \
  -H "Authorization: Bearer $(python -c "import yaml; print(yaml.safe_load(open('config.yaml'))['ai']['api_key'])")" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
```

### C. Embed MINXG as a Python library

```python
import minxg
print(minxg.VERSION)              # "0.11.0"

# Driver engine: temporal operator-field
from minxg.driver import State, DriverEngine, smoothing_field
end, report = DriverEngine([smoothing_field(rate=0.4)]).run(
    State(payload={"x": 0.0, "v": 1.0}), n_steps=24,
)

# Lossless BIE codec: byte-identical round-trip
from minxg.lossless import LosslessCodec
assert LosslessCodec().decompress(
    LosslessCodec().compress(b"payload").payload
) == b"payload"
```

### D. Add a private extension

```python
# ~/.minxg_src/extensions/user/my_ext.py
from multiligua_cli.extensions import ExtensionModule
class MyExt(ExtensionModule):
    NAME = "my-ext"
    DESCRIPTION = "does one thing well"
    EXTENSION_ENABLED = True
```

```bash
minxg ext add ./my_ext.py
minxg ext info my-ext
```

## Troubleshooting

| symptom                                                                 | cause                                                       | fix                                                              |
|-------------------------------------------------------------------------|-------------------------------------------------------------|------------------------------------------------------------------|
| `minxg: command not found` after install                                | editable install put launcher under `~/.local/bin` not on PATH | `export PATH="$HOME/.local/bin:$PATH"` (or use the Termux site)  |
| `dlopen ... cannot locate symbol "minxg_slugify"` on Termux + Py3.13     | old `cpp_core/CMakeLists.txt` link order                    | rebuild with the new cmake; `pip install -e .` after rebuild     |
| `KeyError: 'emoji'` in setup wizard                                     | provider registry entry missing fields                      | fixed in 0.11.0; pull latest                                     |
| `Configuration missing; run minxg setup`                                | first run, `config.yaml` not created                        | run `minxg setup`                                                |
| `OSError: dlopen failed: library not accessible for the namespace`       | SELinux / sandbox blocks shared object load                 | copy the `.so` into syslib path, or use `LD_LIBRARY_PATH`        |
| `RuntimeError: cannot locate symbol "ZSTD_compressBound"`               | linker didn't pull libzstd                                  | `pkg install libzstd`, then rebuild native                       |
| `minxg gateway start: Address already in use`                           | port collision                                              | edit `gateway.port` in `config.yaml`, or stop the other process  |
| `cryptography` import raises `Symbol not found` on Termux               | ABI / arch mismatch in the binary wheel                     | `MINXG_NO_NATIVE=1 minxg ...` (forces pure-Python fallback)      |
| `Provider "<name>" did you mean ...`                                    | typo in `minxg model <name>`                                | re-run `minxg model` (lints the provider name)                   |

If `minxg doctor` exits non-zero, paste the full output in your bug
report — it lists `minxg.__all__`, the operator registry size, native
lib status, and config validation in a fixed-width table.

### Enabling debug logs

```bash
minxg -v setup          # verbose flag
```

The flag raises the root logger to DEBUG, useful for tracing
`extension discovery` and `provider normalisation` paths.

## Experimental surface

Anything labelled `[EXPERIMENTAL]` is **not** part of the supported
CLI surface. Signatures may change, methods may no-op, and entire
classes may disappear between minor versions without changelog
notice. They live in the tree so contributors can find them; do not
build tooling on top of them and do not ingest them into the
stable TUI.

The current experimental exports are reachable through:

```python
from multiligua_cli import features
print(features.list_experimental_exports())
```

In this release (0.11.0) that yields:

```
['QuickFeedback', 'SessionManager', 'SHORTCUTS', 'SilentFeatures',
 'Spinner', 'THEMES', 'context_usage_bar', 'export_to_markdown',
 'get_silent', 'play_notification', 'role_color',
 'share_to_gist', 'welcome_animation']
```

Notable specifics:

* `SilentFeatures.check_updates()` is a **stub** that returns
  `None` — the update-check backend is unfinished.
* `SilentFeatures.keepalive_check()` does a 3-second HEAD against
  `https://api.openai.com/v1/models` — it does *not* authenticate,
  it only checks the endpoint is reachable.
* `SilentFeatures.optimize_memory_index()` requires
  `~/.minxg/memory.db` to exist; if it doesn't, the call is a no-op.
* `SessionManager` / `QuickFeedback` are *not* wired into the TUI
  (saved sessions / feedback are not currently surfaced in the
  shipped chat UI).

The first time you call any of these, a WARNING is logged via the
`features` logger so the experimental status is visible at runtime:

```text
WARNING features: EXPERIMENTAL feature SilentFeatures.disk_usage_report is not part of the stable CLI surface
```

If you genuinely need one of these and would like it promoted to
stable, file an issue with the use-case — that's how a feature
graduates out of `features.py`.

## See also

* `CHANGELOG.md` — per-version release notes
* `CONTRIBUTING`-style guidance lives in `DEVELOPER.md`

## License

MIT. See `LICENSE`.
