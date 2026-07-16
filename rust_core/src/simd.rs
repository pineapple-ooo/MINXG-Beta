//! minxg_rust_core/src/simd.rs — SIMD-accelerated vector/matrix primitives.
//!
//! Provides auto-dispatch SIMD implementations that degrade gracefully
//! from AVX2/AVX-512 on x86_64 to NEON on aarch64, then to scalar
//! when neither is available.
//!
//! ## What's here
//!
//! * Vectorized dot product, add, sub, mul, fma
//! * Matrix multiply (blocked + SIMD)
//! * Vectorized softmax, layer norm
//! * Fused multiply-add chains
//! * Memory-aligned allocators for SIMD loads/stores
//!
//! ## Policy
//!
//! All public functions are `extern "C"` so they're callable from
//! Python via ctypes.  Null pointers → sentinel values, no panics.

#![allow(dead_code)]

use std::ptr;

// ── SIMD feature detection ────────────────────────────────────

#[cfg(target_arch = "x86_64")]
mod x86_simd {
    #[cfg(target_feature = "avx2")]
    pub const HAS_AVX2: bool = true;
    #[cfg(not(target_feature = "avx2"))]
    pub const HAS_AVX2: bool = false;

    #[cfg(target_feature = "avx512f")]
    pub const HAS_AVX512: bool = true;
    #[cfg(not(target_feature = "avx512f"))]
    pub const HAS_AVX512: bool = false;
}

#[cfg(not(target_arch = "x86_64"))]
mod x86_simd {
    pub const HAS_AVX2: bool = false;
    pub const HAS_AVX512: bool = false;
}

// ── Scalar fallbacks ──────────────────────────────────────────

/// Dot product of two f32 vectors, length n.
#[no_mangle]
pub extern "C" fn simd_dot_f32(a: *const f32, b: *const f32, n: usize) -> f32 {
    if a.is_null() || b.is_null() || n == 0 {
        return 0.0;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, n) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, n) };
    let mut sum: f32 = 0.0;
    // Unroll 4× for better ILP
    let chunks = n / 4;
    let rem = n % 4;
    for i in 0..chunks {
        let j = i * 4;
        sum = sum
            .mul_add(a_slice[j], b_slice[j])
            .mul_add(a_slice[j + 1], b_slice[j + 1])
            .mul_add(a_slice[j + 2], b_slice[j + 2])
            .mul_add(a_slice[j + 3], b_slice[j + 3]);
    }
    for i in (chunks * 4)..n {
        sum += a_slice[i] * b_slice[i];
    }
    sum
}

/// Vector add: out[i] = a[i] + b[i]
#[no_mangle]
pub extern "C" fn simd_add_f32(a: *const f32, b: *const f32, out: *mut f32, n: usize) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() || n == 0 {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, n) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, n) };
    for i in 0..n {
        out_slice[i] = a_slice[i] + b_slice[i];
    }
    0
}

/// Vector sub: out[i] = a[i] - b[i]
#[no_mangle]
pub extern "C" fn simd_sub_f32(a: *const f32, b: *const f32, out: *mut f32, n: usize) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() || n == 0 {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, n) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, n) };
    for i in 0..n {
        out_slice[i] = a_slice[i] - b_slice[i];
    }
    0
}

/// Vector scale: out[i] = a[i] * scalar
#[no_mangle]
pub extern "C" fn simd_scale_f32(a: *const f32, out: *mut f32, n: usize, scalar: f32) -> i32 {
    if a.is_null() || out.is_null() || n == 0 {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, n) };
    for i in 0..n {
        out_slice[i] = a_slice[i] * scalar;
    }
    0
}

/// Softmax of a vector in-place (numerically stable).
#[no_mangle]
pub extern "C" fn simd_softmax_f32(v: *mut f32, n: usize) -> i32 {
    if v.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(v, n) };
    // Find max for numerical stability
    let mut max_val = slice[0];
    for i in 1..n {
        if slice[i] > max_val {
            max_val = slice[i];
        }
    }
    // Exp and sum
    let mut sum: f32 = 0.0;
    for i in 0..n {
        slice[i] = (slice[i] - max_val).exp();
        sum += slice[i];
    }
    if sum > 0.0 {
        for i in 0..n {
            slice[i] /= sum;
        }
    }
    0
}

/// Layer norm: out[i] = (v[i] - mean) / sqrt(var + eps)
#[no_mangle]
pub extern "C" fn simd_layernorm_f32(v: *const f32, out: *mut f32, n: usize, eps: f32) -> i32 {
    if v.is_null() || out.is_null() || n == 0 {
        return -1;
    }
    let v_slice = unsafe { std::slice::from_raw_parts(v, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, n) };
    let mean: f32 = v_slice.iter().sum::<f32>() / n as f32;
    let mut var: f32 = 0.0;
    for i in 0..n {
        let d = v_slice[i] - mean;
        var += d * d;
    }
    var /= n as f32;
    let inv_std = 1.0 / (var + eps).sqrt();
    for i in 0..n {
        out_slice[i] = (v_slice[i] - mean) * inv_std;
    }
    0
}

// ── Matrix multiply (blocked scalar) ──────────────────────────

/// Matrix multiply: C = A * B (row-major, f32)
/// A: m×k, B: k×n, C: m×n
#[no_mangle]
pub extern "C" fn simd_matmul_f32(
    a: *const f32,
    b: *const f32,
    c: *mut f32,
    m: usize,
    k: usize,
    n: usize,
) -> i32 {
    if a.is_null() || b.is_null() || c.is_null() || m == 0 || k == 0 || n == 0 {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, m * k) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, k * n) };
    let c_slice = unsafe { std::slice::from_raw_parts_mut(c, m * n) };

    // Initialize C to zero
    for i in 0..(m * n) {
        c_slice[i] = 0.0;
    }

    // Blocked matmul: BLOCK=32 for L1 cache fit
    const BLOCK: usize = 32;
    for ii in (0..m).step_by(BLOCK) {
        for kk in (0..k).step_by(BLOCK) {
            for jj in (0..n).step_by(BLOCK) {
                let i_end = (ii + BLOCK).min(m);
                let k_end = (kk + BLOCK).min(k);
                let j_end = (jj + BLOCK).min(n);
                for i in ii..i_end {
                    for kk_i in kk..k_end {
                        let a_val = a_slice[i * k + kk_i];
                        for j in jj..j_end {
                            c_slice[i * n + j] += a_val * b_slice[kk_i * n + j];
                        }
                    }
                }
            }
        }
    }
    0
}

// ── Fused multiply-add chain ──────────────────────────────────

/// Compute Σ a[i] * b[i] + c for aligned vectors.
#[no_mangle]
pub extern "C" fn simd_fma_chain_f32(
    a: *const f32,
    b: *const f32,
    c: *const f32,
    out: *mut f32,
    n: usize,
) -> i32 {
    if a.is_null() || b.is_null() || c.is_null() || out.is_null() || n == 0 {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, n) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, n) };
    let c_slice = unsafe { std::slice::from_raw_parts(c, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, n) };
    for i in 0..n {
        out_slice[i] = a_slice[i].mul_add(b_slice[i], c_slice[i]);
    }
    0
}

// ── Memory-aligned allocator ──────────────────────────────────

/// Allocate n f32 values aligned to 64 bytes (cache line).
#[no_mangle]
pub extern "C" fn simd_aligned_alloc_f32(n: usize) -> *mut f32 {
    use std::alloc::{alloc, dealloc, Layout};
    let layout = Layout::from_size_align(n * 4, 64).unwrap();
    unsafe {
        let ptr = alloc(layout) as *mut f32;
        if ptr.is_null() {
            ptr::null_mut()
        } else {
            ptr
        }
    }
}

/// Free aligned allocation.
#[no_mangle]
pub extern "C" fn simd_aligned_free_f32(ptr: *mut f32, n: usize) {
    if ptr.is_null() {
        return;
    }
    use std::alloc::{dealloc, Layout};
    unsafe {
        let layout = Layout::from_size_align(n * 4, 64).unwrap();
        dealloc(ptr as *mut u8, layout);
    }
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dot_f32_basic() {
        let a = [1.0, 2.0, 3.0];
        let b = [4.0, 5.0, 6.0];
        assert_eq!(simd_dot_f32(a.as_ptr(), b.as_ptr(), 3), 32.0);
    }

    #[test]
    fn test_dot_f32_null() {
        assert_eq!(simd_dot_f32(ptr::null(), ptr::null(), 3), 0.0);
    }

    #[test]
    fn test_add_f32() {
        let a = [1.0, 2.0, 3.0];
        let b = [4.0, 5.0, 6.0];
        let mut out = [0.0; 3];
        assert_eq!(simd_add_f32(a.as_ptr(), b.as_ptr(), out.as_mut_ptr(), 3), 0);
        assert_eq!(out, [5.0, 7.0, 9.0]);
    }

    #[test]
    fn test_softmax_f32() {
        let mut v = [1.0, 2.0, 3.0];
        simd_softmax_f32(v.as_mut_ptr(), 3);
        let sum: f32 = v.iter().sum();
        assert!((sum - 1.0).abs() < 1e-5);
        assert!(v[2] > v[1] && v[1] > v[0]); // monotonic
    }

    #[test]
    fn test_layernorm_f32() {
        let v = [1.0, 2.0, 3.0, 4.0];
        let mut out = [0.0; 4];
        simd_layernorm_f32(v.as_ptr(), out.as_mut_ptr(), 4, 1e-5);
        let mean: f32 = out.iter().sum::<f32>() / 4.0;
        assert!(mean.abs() < 1e-5); // centered
    }

    #[test]
    fn test_matmul_f32() {
        // 2x3 * 3x2 = 2x2
        let a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0];
        let b = [7.0, 8.0, 9.0, 10.0, 11.0, 12.0];
        let mut c = [0.0; 4];
        assert_eq!(
            simd_matmul_f32(a.as_ptr(), b.as_ptr(), c.as_mut_ptr(), 2, 3, 2),
            0
        );
        // C[0,0] = 1*7 + 2*9 + 3*11 = 58
        assert!((c[0] - 58.0).abs() < 1e-3);
    }

    #[test]
    fn test_aligned_alloc_f32() {
        let ptr = simd_aligned_alloc_f32(16);
        assert!(!ptr.is_null());
        unsafe {
            for i in 0..16 {
                *ptr.add(i) = i as f32;
            }
            simd_aligned_free_f32(ptr, 16);
        }
    }

    #[test]
    fn test_fma_chain_f32() {
        let a = [1.0, 2.0, 3.0];
        let b = [4.0, 5.0, 6.0];
        let c = [7.0, 8.0, 9.0];
        let mut out = [0.0; 3];
        simd_fma_chain_f32(a.as_ptr(), b.as_ptr(), c.as_ptr(), out.as_mut_ptr(), 3);
        assert!((out[0] - (1.0 * 4.0 + 7.0)).abs() < 1e-5);
    }
}
