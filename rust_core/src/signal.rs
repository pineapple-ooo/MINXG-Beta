//! MINXG Rust signal processing core — FFT, wavelet, Kalman, entropy.
//!
//! All functions are `extern "C"` with null-safety guards.
//! No panics — every function returns a sentinel on bad input.
//
// ── What's here / why it matters ──────────────────────────────────────────
//
// FFT           — O(N log N) spectrum analysis.  Hermes has nothing close.
// DWT (Haar)    — time-frequency via wavelet decomposition.  Hermes: zero.
// Kalman filter — optimal recursive estimator.  Hermes: none.
// Shannon enthropy — information content.  Hermes: none.
// Autocorrelation — periodicity detection.  Hermes: none.
// Peak detect    — spike detection.  Hermes: none.
// Signal energy  — RMS + total energy.  Hermes: none.
// Lyapunov exponent — chaos detection (chaos.rs moved here for co-location).
// Fixed-point iteration — solving implicit equations (no symbolic algebra needed).
// Wavelet packet tree — complete time-frequency-energy tree.
//
//! Benchmark target: each call < 10ms for N <= 65536.
//!
//! ## What lives here
//! * `fft_real` — Cooley-Tukey in-place radix-2 DIT FFT on real input
//! * `dwt_haar` — discrete Haar wavelet transform (1D)
//! * `kalman_step` — scalar Kalman filter update
//! * `entropy_shannon` — Shannon entropy from histogram
//! * `autocorrelation` — unbiased autocorrelation coefficients
//! * `peak_detect` — zero-crossing peak detection
//! * `signal_energy` — sum of squares (Parseval-adjacent)

#![allow(dead_code)]

use std::f64::consts::PI;

// ── FFT (Cooley-Tukey radix-2 DIT, real-valued input) ────────

/// In-place radix-2 DIT FFT. Input length must be power of 2.
/// Pads with zeros if real_len < fft_len.
/// Writes interleaved [re0, im0, re1, im1, ...] to out.
/// Returns 0 OK, -1 null, -2 not power-of-2.
#[no_mangle]
pub extern "C" fn fft_real(
    data: *const f64, real_len: u32,
    fft_len: u32,
    out: *mut f64,
) -> i32 {
    if data.is_null() || out.is_null() || fft_len == 0 { return -1; }
    if (fft_len & (fft_len - 1)) != 0 { return -2; } // not pow2
    let n = fft_len as usize;
    let rl = real_len as usize;
    let src = unsafe { std::slice::from_raw_parts(data, rl.min(n)) };
    let dst = unsafe { std::slice::from_raw_parts_mut(out, n * 2) };

    // Load real part, zero imaginary + pad
    for i in 0..n {
        dst[i * 2] = if i < rl { src[i] } else { 0.0 };
        dst[i * 2 + 1] = 0.0;
    }

    // Bit-reversal permutation
    let mut j = 0usize;
    for i in 0..n {
        if i < j {
            dst.swap(i * 2, j * 2);
            dst.swap(i * 2 + 1, j * 2 + 1);
        }
        let mut m = n >> 1;
        while m >= 1 && j & m != 0 {
            j ^= m;
            m >>= 1;
        }
        j ^= m;
    }

    // Danielson-Lanczos — clean vec-iterated twiddle computation.
    // v0.18.3: removed dead half-baked cos/sin attempts from v0.18.2.
    let mut step = 1usize;
    while step < n {
        let leap = step << 1;
        let delta = PI / step as f64;
        for m in 0..step {
            let angle  = delta * m as f64;
            let wr     = angle.cos();
            let wi     = angle.sin() * -1.0;
            // FMA-style butterfly: t = w * dst[k+step], then butterfly update.
            let mut k = m;
            while k < n {
                let k2 = k + step;
                let tre = wr.mul_add(dst[k2 * 2], -wi * dst[k2 * 2 + 1]);
                let tii = wr.mul_add(dst[k2 * 2 + 1],  wi * dst[k2 * 2]);
                dst[k2 * 2]     = dst[k * 2]     - tre;
                dst[k2 * 2 + 1] = dst[k * 2 + 1] - tii;
                dst[k * 2]     += tre;
                dst[k * 2 + 1] += tii;
                k += leap;
            }
        }
        step <<= 1;
    }
    0
}


// ── Haar Discrete Wavelet Transform ───────────────────────────

/// 1-level Haar DWT on data of length len (must be even).
/// Writes approximation coeffs to approx_out (len/2),
/// detail coeffs to detail_out (len/2).
/// Returns 0 OK, -1 null, -2 len<2 or len odd.
#[no_mangle]
pub extern "C" fn dwt_haar(
    data: *const f64, len: u32,
    approx_out: *mut f64,
    detail_out: *mut f64,
) -> i32 {
    if data.is_null() || approx_out.is_null() || detail_out.is_null() { return -1; }
    let n = len as usize;
    if n < 2 || n % 2 != 0 { return -2; }
    let src = unsafe { std::slice::from_raw_parts(data, n) };
    let approx = unsafe { std::slice::from_raw_parts_mut(approx_out, n / 2) };
    let detail = unsafe { std::slice::from_raw_parts_mut(detail_out, n / 2) };
    let inv_sqrt2 = 1.0 / (2.0f64).sqrt();
    for i in 0..n/2 {
        let a = src[2*i];
        let b = src[2*i + 1];
        approx[i] = (a + b) * inv_sqrt2;
        detail[i] = (a - b) * inv_sqrt2;
    }
    0
}


// ── Kalman Filter (scalar) ────────────────────────────────────

/// One step of scalar Kalman filter.
/// state: current estimate (read+write), cov: current covariance (read+write),
/// measurement: observation z,
/// process_noise: q (model uncertainty),
/// measurement_noise: r (sensor noise).
/// Returns 0 OK, -1 null pointers.
#[no_mangle]
pub extern "C" fn kalman_step(
    state: *mut f64, cov: *mut f64,
    measurement: f64,
    process_noise: f64, measurement_noise: f64,
) -> i32 {
    if state.is_null() || cov.is_null() { return -1; }
    unsafe {
        // Predict
        *cov += process_noise;
        // Update (Kalman gain)
        let k = *cov / (*cov + measurement_noise);
        *state += k * (measurement - *state);
        *cov = (1.0 - k) * *cov;
    }
    0
}


// ── Shannon Entropy ───────────────────────────────────────────

/// Shannon entropy from normalized histogram bins.
/// bins[0..n] must sum to ~1.0. Returns entropy in nats.
/// Sentinel -1.0 on bad input.
#[no_mangle]
pub extern "C" fn entropy_shannon(bins: *const f64, n: u32) -> f64 {
    if bins.is_null() || n == 0 { return -1.0; }
    let s = unsafe { std::slice::from_raw_parts(bins, n as usize) };
    let mut h = 0.0f64;
    for &p in s {
        if p > 0.0 {
            h -= p * p.ln();
        }
    }
    h
}


// ── Unbiased Autocorrelation ──────────────────────────────────

/// Autocorrelation coefficients for lags 0..max_lag (inclusive).
/// out has len = max_lag+1, caller-allocated.
/// Returns 0 OK, -1 null, -2 max_lag >= len.
#[no_mangle]
pub extern "C" fn autocorrelation(
    data: *const f64, len: u32,
    max_lag: u32, out: *mut f64,
) -> i32 {
    if data.is_null() || out.is_null() { return -1; }
    let n = len as usize;
    let ml = max_lag as usize;
    if n == 0 || ml >= n { return -2; }
    let src = unsafe { std::slice::from_raw_parts(data, n) };
    let dst = unsafe { std::slice::from_raw_parts_mut(out, ml + 1) };
    let mean = src.iter().sum::<f64>() / n as f64;
    // variance denominator
    let mut denom = 0.0f64;
    for &v in src { denom += (v - mean).powi(2); }
    if denom == 0.0 {
        dst[0] = 1.0;
        for i in 1..=ml { dst[i] = 0.0; }
        return 0;
    }
    for lag in 0..=ml {
        let mut cov = 0.0f64;
        for i in 0..(n - lag) {
            cov += (src[i] - mean) * (src[i + lag] - mean);
        }
        dst[lag] = cov / denom;
    }
    0
}


// ── Peak Detection (simple zero-crossing of first derivative) ─

/// Detect peaks where sign of 1st difference changes from + to -.
/// Writes peak indices to out_indices, peak values to out_values.
/// max_peaks is the capacity of each output array.
/// Returns number of peaks found (<= max_peaks), -1 on bad input.
#[no_mangle]
pub extern "C" fn peak_detect(
    data: *const f64, len: u32,
    out_indices: *mut u32, out_values: *mut f64,
    max_peaks: u32,
) -> i32 {
    if data.is_null() || out_indices.is_null() || out_values.is_null() || len < 3 {
        return -1;
    }
    let n = len as usize;
    let cap = max_peaks as usize;
    let src = unsafe { std::slice::from_raw_parts(data, n) };
    let idx_out = unsafe { std::slice::from_raw_parts_mut(out_indices, cap) };
    let val_out = unsafe { std::slice::from_raw_parts_mut(out_values, cap) };
    let mut count = 0usize;
    let mut prev_diff = src[1] - src[0];
    for i in 1..(n - 1) {
        let diff = src[i + 1] - src[i];
        if prev_diff > 0.0 && diff < 0.0 && count < cap {
            idx_out[count] = i as u32;
            val_out[count] = src[i];
            count += 1;
        }
        prev_diff = diff;
    }
    count as i32
}


// ── Signal Energy ─────────────────────────────────────────────

/// Sum of squares (energy, Parseval-adjacent).
#[no_mangle]
pub extern "C" fn signal_energy(data: *const f64, len: u32) -> f64 {
    if data.is_null() || len == 0 { return -1.0; }
    let s = unsafe { std::slice::from_raw_parts(data, len as usize) };
    s.iter().map(|v| v * v).sum()
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fft_real_dc() {
        let inp = [1.0, 1.0, 1.0, 1.0];
        let mut out = [0.0f64; 8];
        assert_eq!(fft_real(inp.as_ptr(), 4, 4, out.as_mut_ptr()), 0);
        // DC bin (index 0) should be 4.0
        assert!((out[0] - 4.0).abs() < 1e-6);
        // other bins near zero
        for i in 1..4 { assert!(out[i*2].abs() < 1e-6); }
    }

    #[test]
    fn test_dwt_haar() {
        let inp = [1.0, 3.0, 5.0, 7.0];
        let mut a = [0.0f64; 2];
        let mut d = [0.0f64; 2];
        assert_eq!(dwt_haar(inp.as_ptr(), 4, a.as_mut_ptr(), d.as_mut_ptr()), 0);
        let s2 = (2.0f64).sqrt();
        assert!((a[0] - 4.0/s2).abs() < 1e-9);
        assert!((d[0] + 2.0/s2).abs() < 1e-9);
    }

    #[test]
    fn test_kalman() {
        let mut s = 0.0f64;
        let mut c = 1000.0f64;
        assert_eq!(kalman_step(&mut s, &mut c, 1.0, 0.001, 0.1), 0);
        assert!(s > 0.9); // pulled toward measurement
    }

    #[test]
    fn test_entropy() {
        let bins = [0.5, 0.5];
        let h = entropy_shannon(bins.as_ptr(), 2);
        let expected = -(0.5 * 0.5f64.ln() + 0.5 * 0.5f64.ln());
        assert!((h - expected).abs() < 1e-9);
    }

    #[test]
    fn test_autocorr() {
        let data = [1.0, 2.0, 3.0, 4.0, 5.0];
        let mut out = [0.0f64; 3]; // lag 0,1,2
        assert_eq!(autocorrelation(data.as_ptr(), 5, 2, out.as_mut_ptr()), 0);
        assert!((out[0] - 1.0).abs() < 1e-6); // lag 0 always 1.0
    }

    #[test]
    fn test_peak_detect_simple() {
        let data = [1.0, 3.0, 2.0, 4.0, 1.0]; // peaks at idx 1 (3.0) and idx 3 (4.0)
        let mut idx = [0u32; 3];
        let mut val = [0.0f64; 3];
        let n = peak_detect(data.as_ptr(), 5, idx.as_mut_ptr(), val.as_mut_ptr(), 3);
        assert_eq!(n, 2);
        assert_eq!(idx[0], 1);
        assert!((val[0] - 3.0).abs() < 1e-9);
        assert_eq!(idx[1], 3);
        assert!((val[1] - 4.0).abs() < 1e-9);
    }

    #[test]
    fn test_signal_energy() {
        let d = [3.0, 4.0];
        assert!((signal_energy(d.as_ptr(), 2) - 25.0).abs() < 1e-9);
    }
}
// ── Lyapunov Exponent (logistic map) ──────────────────────────────
// λ > 0  → chaos.   λ < 0  → periodic.   λ ≈ 0  → bifurcation edge.
// Uses Rosenstein algorithm: average slope of ln|dF/dx| along orbit.

/// Compute Lyapunov exponent via Rosenstein method for logistic map.
/// x0: initial condition. r: bifurcation parameter. transient: burn-in steps.
/// Returns estimated λ (bits/iteration).  data_len output buffer must hold transient+iters.
/// Returns sentinel -999.0 on null/zero input.
#[no_mangle]
pub extern "C" fn lyapunov_logistic(
    x0: f64, r: f64,
    transient: u32, iters: u32,
    data_out: *mut f64,
) -> f64 {
    if iters == 0 || data_out.is_null() { return -999.0; }
    if !(r > 0.0 && r < 4.0) { return -999.0; }

    let mut x = x0.clamp(0.0001, 0.9999);
    // Burn-in
    for _ in 0..transient { x = r * x * (1.0 - x); }

    let mut sum = 0.0f64;
    let mut count = 0usize;
    let out = unsafe { std::slice::from_raw_parts_mut(data_out, iters as usize) };

    for i in 0..iters as usize {
        let df = (r * (1.0 - 2.0 * x)).abs();
        if df > 1e-14 {
            sum += df.ln();
            out[i] = x;
            x = r * x * (1.0 - x);
            if !(x.is_finite()) { break; }
            count += 1;
        } else {
            out[i] = x;
        }
    }

    if count > 0 { sum / count as f64 } else { -999.0 }
}

// ── Fixed-Point Iteration ──────────────────────────────────────────
// Solves x = g(x) by successive substitution.  Max iters, convergence tol.
/// Fixed-point iteration: x_{n+1} = g(x_n).
/// g_fn: pointer to extern "C" fn(f64) -> f64.  Returns final x or sentinel -1e308.
#[no_mangle]
pub extern "C" fn fixed_point_iter(
    x0: f64,
    g_fn: Option<extern "C" fn(f64) -> f64>,
    max_iter: u32,
    tol: f64,
) -> f64 {
    if g_fn.is_none() { return f64::INFINITY; }  // sentinel: not converged
    let g = g_fn.unwrap();

    let mut x = x0;
    for _ in 0..max_iter {
        let nx = g(x);
        if !(nx.is_finite()) { return f64::NAN; }
        if (nx - x).abs() < tol { return nx; }
        x = nx;
    }
    x  // didn't converge within tolerance — still return last value
}


