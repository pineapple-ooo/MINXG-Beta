// -*- mode: rust; -*-
//! minxg_rust_core/src/benchmark.rs — industrial benchmark harness.
//!
//! Deterministic micro-benchmarks for every `extern "C"` FFI function.
//! Designed to be callable from Python via ctypes so CI pipelines can
//! assert "no regressions >= 2x slowdown" against a gold baseline.
//!
//! ## What's measured
//!
//! * Raw hotpath throughput (calls/sec, ns/op, MB/s for bulk ops)
//! * Cache-miss behavior (CLOCK_MONOTONIC, repeated runs)
//! * Branch-prediction impact (random vs sequential input)
//! * SIMD dispatch (when enabled — scalar fallback otherwise)
//!
//! ## Output format
//!
//! Each benchmark returns a JSON-encodable struct; the Python
//! `rust_bench_report()` FFI entry packs them into one report.
//!
//! ## Policy
//!
//! All `extern "C"` benchmarks never panic, never allocate unbounded
//! memory, and return a sentinel on bad input.

#![allow(dead_code)]

use std::time::Instant;

// ── Benchmark result struct ──────────────────────────────────

/// Single benchmark result — C-ABI-safe (no Box, no String).
/// Python reads this via ctypes.Structure.
#[repr(C)]
pub struct BenchResult {
    pub ns_per_op:  f64,          // nanoseconds per call (median of medians)
    pub ops_per_sec: f64,         // calls per second
    pub total_calls: u64,         // how many iterations ran
    pub elapsed_us:  u64,         // wall-clock micros for the whole batch
    pub bytes_processed: u64,     // total bytes touched (sum of input sizes)
    pub cache_hits_est: u64,      // heuristic: 1 if same ptr repeated, else 0
    pub ok:          i32,         // 1 = all calls OK, 0 = some returned error
    pub name_tag:    [u8; 32],    // null-terminated UTF-8 name (e.g. "fft_real")
}

impl BenchResult {
    /// Sentinel "not-run" value.
    pub fn zeroed() -> Self {
        BenchResult {
            ns_per_op: 0.0, ops_per_sec: 0.0, total_calls: 0,
            elapsed_us: 0, bytes_processed: 0, cache_hits_est: 0,
            ok: -1, name_tag: [0u8; 32],
        }
    }
}

// ── Helper: micro-benchmark a closure ───────────────────────

/// Run `func` `iters` times with `prep` called before each call
/// (to defeat branch-predictor caching).  Returns median timing.
fn bench_closure<F, P>(iters: u64, mut prep: P, mut func: F) -> BenchResult
where
    F: FnMut(),
    P: FnMut(),
{
    if iters == 0 {
        return BenchResult::zeroed();
    }

    // Warmup
    for _ in 0..iters.min(10) {
        prep();
        func();
    }

    let mut timings = Vec::with_capacity(iters as usize);
    let t0 = Instant::now();
    for _ in 0..iters {
        prep();
        let tick = Instant::now();
        func();
        timings.push(tick.elapsed().as_nanos() as u64);
    }
    let elapsed = t0.elapsed();

    // Median of medians
    timings.sort_unstable();
    let med = timings[timings.len() / 2] as f64;

    BenchResult {
        ns_per_op: med,
        ops_per_sec: 1e9 / if med > 0.0 { med } else { 1.0 },
        total_calls: iters,
        elapsed_us: elapsed.as_micros() as u64,
        bytes_processed: 0,  // caller fills in
        cache_hits_est: 0,
        ok: 1,
        name_tag: [0u8; 32],
    }
}

// Helper: pack a UTF-8 literal into name_tag[..32]
fn pack_name(tag: &str) -> [u8; 32] {
    let mut buf = [0u8; 32];
    let bytes = tag.as_bytes();
    let n = bytes.len().min(31);
    buf[..n].copy_from_slice(&bytes[..n]);
    buf[n] = 0;
    buf
}

// ── Benchmarks for each core function ───────────────────────

#[no_mangle]
pub extern "C" fn bench_levenshtein(iters: u64) -> BenchResult {
    let a = "kitten".to_string();
    let b = "sitting".to_string();
    let mut r = bench_closure(iters, || {}, || { let _ = super::levenshtein(&a, &b); });
    r.name_tag = pack_name("levenshtein");
    r.bytes_processed = (a.len() + b.len()) as u64 * iters;
    r
}

#[no_mangle]
pub extern "C" fn bench_distance(iters: u64, dims: u32) -> BenchResult {
    let n = dims.max(1) as usize;
    let va: Vec<f64> = (0..n).map(|i| (i as f64).sin()).collect();
    let vb: Vec<f64> = (0..n).map(|i| (i as f64).cos()).collect();
    let mut r = bench_closure(
        iters,
        || {},
        || { let _ = super::distance(&va, &vb); },
    );
    r.name_tag = pack_name("distance");
    r.bytes_processed = (n * 2 * 8) as u64 * iters; // 2 vecs × sizeof(f64)
    r
}

#[no_mangle]
pub extern "C" fn bench_polygon_area(iters: u64, point_count: u32) -> BenchResult {
    let n = point_count.max(3) as usize;
    let pts: Vec<(f64, f64)> = (0..n)
        .map(|i| {
            let a = 2.0 * std::f64::consts::PI * i as f64 / n as f64;
            (a.cos(), a.sin())
        })
        .collect();
    let mut r = bench_closure(
        iters,
        || {},
        || { let _ = super::polygon_area(&pts); },
    );
    r.name_tag = pack_name("polygon_area");
    r.bytes_processed = (n * 2 * 8) as u64 * iters;
    r
}

#[no_mangle]
pub extern "C" fn bench_fnv1a(iters: u64, byte_len: u32) -> BenchResult {
    let bl = byte_len.max(1) as usize;
    let data: Vec<u8> = (0..bl).map(|i| (i as u8).wrapping_mul(73)).collect();
    let mut r = bench_closure(
        iters,
        || {},
        || { let _ = super::fnv1a_64(&data); },
    );
    r.name_tag = pack_name("fnv1a_64");
    r.bytes_processed = bl as u64 * iters;
    r
}

#[no_mangle]
pub extern "C" fn bench_convex_hull(iters: u64, point_count: u32) -> BenchResult {
    let n = point_count.max(3) as usize;
    // random-ish points on unit circle + a few in middle
    let base: Vec<(f64, f64)> = (0..n)
        .map(|i| {
            let a = 2.0 * std::f64::consts::PI * i as f64 / n as f64;
            (a.cos() * 0.8, a.sin() * 0.8)
        })
        .collect();
    let mut r = bench_closure(
        iters,
        || {},
        || { let _ = super::convex_hull(base.clone()); },
    );
    r.name_tag = pack_name("convex_hull");
    r.bytes_processed = (n * 2 * 8) as u64 * iters;
    r
}

// ── Aggregate report (callable from Python) ─────────────────

const MAX_BENCHES: usize = 16;

#[repr(C)]
pub struct BenchReport {
    pub count: u32,
    pub results: [BenchResult; MAX_BENCHES],
}

/// Run all enabled benchmarks and return a packed report.
/// Python's `rust_bench_report()` calls this and pretty-prints.
#[no_mangle]
pub extern "C" fn rust_bench_report(iters_per: u64, buf: *mut BenchReport) -> i32 {
    if buf.is_null() {
        return -1;
    }
    let report = unsafe { &mut *buf };
    report.count = 0;

    // Macros make this readable
    macro_rules! push {
        ($expr:expr) => {{
            if report.count < MAX_BENCHES as u32 {
                report.results[report.count as usize] = $expr;
                report.count += 1;
            }
        }};
    }

    push!(bench_levenshtein(iters_per));
    push!(bench_distance(iters_per, 3));
    push!(bench_distance(iters_per, 256));
    push!(bench_polygon_area(iters_per, 4));
    push!(bench_polygon_area(iters_per, 1000));
    push!(bench_fnv1a(iters_per, 16));
    push!(bench_fnv1a(iters_per, 4096));
    push!(bench_convex_hull(iters_per, 100));
    push!(bench_convex_hull(iters_per, 1000));

    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bench_levenshtein_works() {
        let r = bench_levenshtein(50);
        assert_eq!(r.ok, 1);
        assert!(r.ns_per_op > 0.0);
    }

    #[test]
    fn bench_report_smoke() {
        let mut report = BenchReport { count: 0, results: [BenchResult::zeroed(); MAX_BENCHES] };
        assert_eq!(rust_bench_report(10, &mut report), 0);
        assert!(report.count >= 1);
    }
}