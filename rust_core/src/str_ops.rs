//! String / hashing / parallelism ops offloaded from Python.
//!
//! All functions are `extern "C"`, no-leak, fixed-buffer.
//!
//! Pseudocode summary:
//!
//!   str_hash64(s) -> u64              : FNV-1a 64-bit; -1 on null.
//!   str_count(_bytes, want) -> u32    : count bytes equal to `want` in slice
//!   str_lower_ascii(buf, len) -> i32  : in-place ASCII lowercasing
//!   str_utf8_validate(buf, len) -> i32: 0 ok, -1 invalid UTF-8
//!   vec_sum_sq(data, n) -> f64        : sum(x_i^2), -1 on bad in
//!   vec_dot(a, b, n) -> f64           : dot product
//!   vec_normalize(data, n) -> i32     : in-place normalize; 0 ok, -1 on zero len
//!   parallel_map_u64(data, n, f)      : runs f(x)=x^2+x over each element; not in FFI block — internal helper

#![allow(dead_code)]
use std::cmp::min;
use std::sync::mpsc;

/// FNV-1a 64-bit hash. -1 on null.
#[no_mangle]
pub extern "C" fn str_hash64(s: *const u8, len: u32) -> u64 {
    if s.is_null() {
        return u64::MAX;
    }
    let slice = unsafe { std::slice::from_raw_parts(s, len as usize) };
    let mut h: u64 = 0xcbf29ce484222325;
    for &b in slice {
        h ^= b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

/// Count bytes equal to `want`.
#[no_mangle]
pub extern "C" fn str_count(s: *const u8, len: u32, want: u8) -> u32 {
    if s.is_null() {
        return 0;
    }
    let slice = unsafe { std::slice::from_raw_parts(s, len as usize) };
    slice.iter().filter(|&&b| b == want).count() as u32
}

/// In-place ASCII lower-case. Bytes not mutated for non-ASCII above 127.
/// Returns 0 ok, -1 on bad input.
#[no_mangle]
pub extern "C" fn str_lower_ascii(s: *mut u8, len: u32) -> i32 {
    if s.is_null() || len == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(s, len as usize) };
    for b in slice {
        if *b >= b'A' && *b <= b'Z' {
            *b += 32;
        }
    }
    0
}

/// Validate UTF-8 strictly. Returns 0 ok, -1 invalid.
#[no_mangle]
pub extern "C" fn str_utf8_validate(s: *const u8, len: u32) -> i32 {
    if s.is_null() {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(s, len as usize) };
    match std::str::from_utf8(slice) {
        Ok(_) => 0,
        Err(_) => -1,
    }
}

/// Sum of squares. -1 on bad input.
#[no_mangle]
pub extern "C" fn vec_sum_sq(data: *const f64, n: u32) -> f64 {
    if data.is_null() || n == 0 {
        return -1.0;
    }
    let s = unsafe { std::slice::from_raw_parts(data, n as usize) };
    s.iter().map(|&v| v * v).sum()
}

/// Dot product.
#[no_mangle]
pub extern "C" fn vec_dot(a: *const f64, b: *const f64, n: u32) -> f64 {
    if a.is_null() || b.is_null() || n == 0 {
        return -1.0;
    }
    let va = unsafe { std::slice::from_raw_parts(a, n as usize) };
    let vb = unsafe { std::slice::from_raw_parts(b, n as usize) };
    let mut acc = 0.0f64;
    for i in 0..n as usize {
        acc += va[i] * vb[i];
    }
    acc
}

/// In-place normalise (L2). 0 ok, -1 on bad.
#[no_mangle]
pub extern "C" fn vec_normalize(data: *mut f64, n: u32) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let s = unsafe { std::slice::from_raw_parts(data, n as usize) };
    let sumsq: f64 = s.iter().map(|&v| v * v).sum();
    let n_f = sumsq.sqrt();
    if n_f == 0.0 {
        return -1;
    }
    let s_mut = unsafe { std::slice::from_raw_parts_mut(data, n as usize) };
    for v in s_mut {
        *v /= n_f;
    }
    0
}

/// Sequential map+reduce: applies `(x*x + x)` to each element, accumulates sum.
/// Useful test for FFI-from-Python behaviour. -1.0 on bad.
#[no_mangle]
pub extern "C" fn vec_fused_sqadd_sum(data: *const f64, n: u32) -> f64 {
    if data.is_null() || n == 0 {
        return -1.0;
    }
    let s = unsafe { std::slice::from_raw_parts(data, n as usize) };
    let acc: f64 = s.iter().map(|&v| v * v + v).sum();
    acc
}

// ─── Parallel helpers (no FFI export; used internally + tests) ────────────────

/// Sum `vec_fused_sqadd_sum` over chunks using std::thread.
/// Reasonable scaling on a few thousand elements.
pub fn parallel_fused_sum(data: &[f64]) -> f64 {
    let chunks = min(8, data.len().max(1));
    let chunk_size = data.len() / chunks.max(1);
    if chunk_size == 0 {
        return data.iter().map(|&v| v * v + v).sum();
    }
    let (tx, rx) = mpsc::channel();
    let mut start = 0usize;
    while start < data.len() {
        let end = (start + chunk_size).min(data.len());
        let slice = data[start..end].to_vec();
        let tx_cl = tx.clone();
        std::thread::spawn(move || {
            let s: f64 = slice.iter().map(|&v| v * v + v).sum();
            let _ = tx_cl.send(s);
        });
        start = end;
    }
    drop(tx);
    let mut total = 0.0f64;
    for r in rx {
        total += r;
    }
    total
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn hash_basic() {
        let s = b"hello";
        let h = str_hash64(s.as_ptr(), 5);
        assert_ne!(h, u64::MAX);
        assert_eq!(h, str_hash64(s.as_ptr(), 5), "stable hash");
    }
    #[test]
    fn count_basic() {
        let s = b"hello hello hello";
        let n = str_count(s.as_ptr(), s.len() as u32, b'l');
        assert_eq!(n, 3);
    }
    #[test]
    fn lower_basic() {
        let mut s = b"HELLO WORLD".to_vec();
        assert_eq!(str_lower_ascii(s.as_mut_ptr(), s.len() as u32), 0);
        assert_eq!(s, b"hello world");
    }
    #[test]
    fn utf8_basic() {
        let ok = b"abc";
        let bad = &[0xffu8, 0xfe, 0xfd];
        assert_eq!(str_utf8_validate(ok.as_ptr(), ok.len() as u32), 0);
        assert_eq!(str_utf8_validate(bad.as_ptr(), bad.len() as u32), -1);
    }
    #[test]
    fn sumsq() {
        let v = [1.0, 2.0, 3.0, 4.0];
        let s = vec_sum_sq(v.as_ptr(), 4);
        assert!((s - 30.0).abs() < 1e-9);
    }
    #[test]
    fn dot() {
        let a = [1.0, 2.0, 3.0];
        let b = [4.0, 5.0, 6.0];
        let d = vec_dot(a.as_ptr(), b.as_ptr(), 3);
        assert!((d - 32.0).abs() < 1e-9);
    }
    #[test]
    fn normalize() {
        let mut v = [3.0, 0.0, 4.0];
        assert_eq!(vec_normalize(v.as_mut_ptr(), 3), 0);
        assert!((v[0] - 0.6).abs() < 1e-9);
        assert!((v[2] - 0.8).abs() < 1e-9);
    }
    #[test]
    fn parallel_eq_single() {
        let data: Vec<f64> = (0..1000).map(|i| i as f64 * 0.5).collect();
        let s_single = data.iter().map(|&v| v * v + v).sum::<f64>();
        let s_par = parallel_fused_sum(&data);
        assert!((s_single - s_par).abs() < 1e-3);
    }
}
