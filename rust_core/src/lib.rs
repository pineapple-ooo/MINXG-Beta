//! MINXG Rust Core — Zero-overhead mathematical operators with C FFI bridge.
//!
//! Design principles:
//! 1. **No allocation in hot paths** — pre-allocated buffers, stack arrays.
//! 2. **Memory safe by construction** — no raw pointer arithmetic, no leaks.
//! 3. **C FFI via `extern "C"`** — callable from Python ctypes/cffi, Go cgo, Java JNI.
//! 4. **Zero-cost abstractions** — Rust's type system enforces invariants at compile time.
//! 5. **Pass-by-reference** — large matrices/slices borrow via FFI, never copied.
//!
//! Operators implemented (v0.16.0):
//! - GA geometric product, outer/inner/fat-dot, rotor application
//! - Driver engine: RK4/RK45 integration, Lyapunov exponent tracking
//! - Chaos: logistic map, Lorenz attractor, IFS fractal
//! - Fiber: parallel transport, connection forms
//! - SymbDiff: Jet (truncated Taylor), Lie bracket
//! - Misc: sha256 (wrapper), slotmap memory pool

pub mod ga; // Geometric Algebra (multivectors, rotors)
pub mod driver; // Driver engine (RK4/RK45, Lyapunov)
pub mod chaos; // Dynamical systems, fractals
pub mod fiber; // Fiber bundles, connections
pub mod symbdiff; // Symbolic differential algebra (Jets, Lie brackets)
pub mod ffi; // extern "C" exports + Python-friendly wrappers
pub mod mempool; // Arena-backed slotmap (zero-leak shared memory)
pub mod math_ops; // High-performance vector/matrix operations

/// Version synced with minxg._version
pub const VERSION: &str = "0.16.0";

/// Number of mathematical operators in the Rust core
pub const RUST_MATH_OPERATORS: u32 = 42;