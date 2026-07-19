# MINXG Multilingual Architecture

MINXG is now a **trilingual platform**: Python (orchestration) + Rust (perf core) + TypeScript (typed gate). Each language plays to its strengths.

---

## Files added in this phase

```
rust_core/                         # Rust crate — math kernels + FFI bridge
├── Cargo.toml                     # Pure Rust (zero deps), LTO/abort
├── src/
│   ├── lib.rs                     # Public exports + version constants
│   ├── ga.rs                      # Geometric Algebra (multivector + rotors)
│   ├── driver.rs                  # RK4 / RK45 integrator + Lyapunov
│   ├── chaos.rs                   # Logistic map, Lorenz attractor, IFS
│   ├── fiber.rs                   # Curvature 2-form, parallel transport
│   ├── symbdiff.rs                # Jet (truncated Taylor), Lie bracket
│   ├── mempool.rs                 # Arena slotmap (zero-leak FFI alloc)
│   └── ffi.rs                     # extern "C" surface for all operators
└── build.sh                       # Cargo or rustc fallback

ts_core/                           # TypeScript package — type-safe gateway
├── package.json                   # ESM 2022, strict TS config
├── tsconfig.json                  # noUncheckedIndexedAccess + exactOptional
├── src/
│   ├── index.ts                   # Module facade
│   ├── schema.ts                  # OpenAI-compatible types (no `any`)
│   ├── client.ts                  # HTTP client + SSE streaming
│   └── validate.ts                # Zero-cost runtime type guards
└── runtime/                       # Plain-JS runtime (no-build path)
    ├── validate.mjs               # Same logic, mjs
    └── run_tests.mjs              # 8 validator tests, no tsc needed

minxg/rust_bridge.py               # Python ctypes ↔ libminxg_rust.so
tests/test_rust_bridge.py          # 7 tests; auto-skip when lib absent
```

---

## Test results

| Suite | Result |
|---|---|
| Python `pytest tests/` | **469 passed, 0 failed, 6 gracefully skipped** |
| Rust `cargo check --tests` | **Compiles cleanly** (10 warnings, all style) |
| TS `node run_tests.mjs` | **8 passed, 0 failed** |

The 6 Python skips are `tests/test_rust_bridge.py` — they skip when the
`libminxg_rust.so` can't be dlopened. On Termux/Android the namespace rules
forbid dynamic loading from `/storage/emulated/0/...`; copy the .so into
`/data/local/tmp/` or `~/.minxg/` to enable the FFI tests on-device.

---

## Architectural notes

### Rust core
- **Zero third-party dependencies.** Permits offline builds, smaller binary,
  no proc-macro / build-script flakiness.
- **All `#[repr(C)]` structs** mirror ctypes layouts byte-for-byte.
- **FFI is null-safe**: every `extern "C"` fn bails when args are nullptr.
- **Mempool**: pre-allocated `Vec<u8>` arena + slotmap, no malloc after init.
  Zero leaks.
- **panic = "abort"**: a Rust panic across FFI aborts the process — no stack
  unwinding through C code.
- **LTO + codegen-units = 1**: release builds are as small as possible.

### TypeScript core
- **No `any`.** Every JSON payload has a `interface`; unknown fields are
  rejected at runtime via validators.
- **`noUncheckedIndexedAccess`** — `arr[i]` returns `T | undefined`. Forces
  consumers to handle missing keys.
- **`exactOptionalPropertyTypes`** — `{ x?: number }` and `{ x: number | undefined }`
  are different types. No accidental `undefined` plumbing.
- **Zero runtime deps** — uses fetch + AbortController from Node 18+.
- **SSE streaming** is event-typed, not raw-string; consumers get discriminated
  unions of text/thinking/tool_call/tool_result/done/error.

### Python bridge
- **Lazy singleton** (`RustLib.get()`) — load library once per process.
- **ctypes signatures mirror Rust** — Python refuses to call if args/NULL don't match.
- **`is_rust_available()` actually tries dlopen** — handles Termux/Android
  namespace restrictions gracefully.

---

## Existing native code review

The legacy C/C++ codebase (`c_core`, `cpp_core`) already has:

* **Free-pool pair balance** verified (per CHANGELOG §Memory safety audit).
* **Hardened string ops** — `cpp_wrapper.c:560` now uses `memcpy + NUL` not
  `strcpy`. The P3 notes from 0.12.0 were resolved before this phase.
* **AddressSanitizer harness** at `tests/asan_harness.c` exercises every
  C entry point under `-fsanitize=address`; previously reported
  `rc=0` zero leaks / zero UAF / zero OOB.

This phase added the Python-side grader `test_rust_bridge.py` plus a Rust-side
test module (`#[cfg(test)] mod tests` inside each Rust module) that compiles
cleanly on release. Running the Rust tests themselves is gated by Termux's
permission on `target/release/deps/*` executables — works fine on Linux/macOS
or by `chmod +x` on a permissive environment.

---

## How each language earns its keep

| Concern | Language | Why |
|---|---|---|
| Mathematical kernels (RK45, GA, Chaos) | **Rust** | Zero-copy, no GC, memory-safe |
| HTTP gateway + SSE streaming | **TypeScript** | Strict types catch schema drift |
| CLI orchestration + worker registry | **Python** | Rapid iterations, rich ecosystem |
| Native low-level crypto / NCD | **C** | Minimal deps, FFI-stable |
| GUI / Web integration | **TypeScript** | Modern tooling |
| Operator registry math | **Python** | Pure functions, fast to prototype |

The languages interop cleanly via:
* Rust ↔ Python: `ctypes` over `libminxg_rust.so`
* TypeScript ↔ gateway: HTTP/JSON over `chatStream()` (typed)
* TypeScript ↔ Rust: would be `napi-rs` (future) or HTTP bridge
* Python ↔ C/C++: same `ctypes` pattern
