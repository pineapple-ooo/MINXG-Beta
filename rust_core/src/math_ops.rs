//! MINXG Rust Core — math offloaded from Python
//!
//! Pseudocode implemented here (exact functions):
//!
//! ```
//! vec_mean(data, n) -> f64
//!   if null or n==0: return -1.0
//!   return sum(data[0..n]) / n
//!
//! vec_std(data, n) -> f64
//!   m = vec_mean(data, n); if m < 0: return m
//!   return sqrt( sum((x - m)^2) / n )
//!
//! vec_minmax(data, n, out_min, out_max) -> i32
//!   if any null or n==0: return -1
//!   scan for min/max; write results; return 0
//!
//! vec_correlation(a, b, n) -> f64
//!   if any null or n==0: return -1.0
//!   Pearson r = sum((a_i-a_m)*(b_i-b_m)) / sqrt(sum_sq_a * sum_sq_b)
//!   if denominator == 0: return 0.0
//!
//! mat_mul(a, ar, ac, b, br, bc, out) -> i32
//!   if any null: return -1
//!   if ac != br: return -2
//!   C[i][j] = sum_k a[i][k] * b[k][j]
//!   return 0
//! ```

#![allow(dead_code)]

/// Mean. Error sentinel: -1.0.
#[no_mangle]
pub extern "C" fn vec_mean(data: *const f64, n: u32) -> f64 {
    if data.is_null() || n == 0 {
        return -1.0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n as usize) };
    slice.iter().sum::<f64>() / n as f64
}

/// Population standard deviation. Propagates mean error (-1.0).
#[no_mangle]
pub extern "C" fn vec_std(data: *const f64, n: u32) -> f64 {
    if data.is_null() || n == 0 {
        return -1.0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n as usize) };
    let m = slice.iter().sum::<f64>() / n as f64;
    if m < -0.5 {
        return m;
    }
    let sum_sq: f64 = slice.iter().map(|&v| (v - m).powi(2)).sum();
    (sum_sq / n as f64).sqrt()
}

/// Min/max in one pass. Returns 0 OK, -1 on bad input.
#[no_mangle]
pub extern "C" fn vec_minmax(
    data: *const f64,
    n: u32,
    out_min: *mut f64,
    out_max: *mut f64,
) -> i32 {
    if data.is_null() || out_min.is_null() || out_max.is_null() || n == 0 {
        return -1;
    }
    let s = unsafe { std::slice::from_raw_parts(data, n as usize) };
    unsafe {
        *out_min = s[0];
        *out_max = s[0];
    }
    for &v in &s[1..] {
        if v < unsafe { *out_min } {
            unsafe { *out_min = v; }
        }
        if v > unsafe { *out_max } {
            unsafe { *out_max = v; }
        }
    }
    0
}

/// Pearson correlation coefficient.
/// Returns -1.0 on bad input, 0.0 when either vector is constant.
#[no_mangle]
pub extern "C" fn vec_correlation(
    a: *const f64,
    b: *const f64,
    n: u32,
) -> f64 {
    if a.is_null() || b.is_null() || n == 0 {
        return -1.0;
    }
    let va = unsafe { std::slice::from_raw_parts(a, n as usize) };
    let vb = unsafe { std::slice::from_raw_parts(b, n as usize) };
    let ma = va.iter().sum::<f64>() / n as f64;
    let mb = vb.iter().sum::<f64>() / n as f64;
    let mut num = 0.0f64;
    let mut da_sum = 0.0f64;
    let mut db_sum = 0.0f64;
    for i in 0..n as usize {
        let da = va[i] - ma;
        let db = vb[i] - mb;
        num += da * db;
        da_sum += da * da;
        db_sum += db * db;
    }
    let den = (da_sum * db_sum).sqrt();
    if den == 0.0 {
        return 0.0;
    }
    num / den
}

/// Row-major matrix multiply: out = a * b
/// a: a_rows x a_cols,  b: b_rows x b_cols (must satisfy a_cols == b_rows)
/// out: caller-allocated length a_rows * b_cols
/// Returns: 0 OK, -1 null ptr, -2 dim mismatch
#[no_mangle]
pub extern "C" fn mat_mul(
    a: *const f64,
    a_rows: u32,
    a_cols: u32,
    b: *const f64,
    b_rows: u32,
    b_cols: u32,
    out: *mut f64,
) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() {
        return -1;
    }
    if a_cols != b_rows {
        return -2;
    }
    let a = unsafe { std::slice::from_raw_parts(a, (a_rows * a_cols) as usize) };
    let b = unsafe { std::slice::from_raw_parts(b, (b_rows * b_cols) as usize) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, (a_rows * b_cols) as usize) };

    for i in 0..a_rows as usize {
        for j in 0..b_cols as usize {
            let mut s = 0.0f64;
            for k in 0..a_cols as usize {
                s += a[i * a_cols as usize + k] * b[k * b_cols as usize + j];
            }
            out[i * b_cols as usize + j] = s;
        }
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn mean() {
        let v = [1.0, 2.0, 3.0, 4.0];
        assert!((vec_mean(v.as_ptr(), 4) - 2.5).abs() < 1e-9);
    }
    #[test]
    fn std_dev() {
        let v = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
        let s = vec_std(v.as_ptr(), 8);
        assert!((s - 2.0).abs() < 1e-9);
    }
    #[test]
    fn minmax() {
        let v = [-3.0, 0.0, 5.0, 2.0];
        let mut mn = 0.0f64;
        let mut mx = 0.0f64;
        assert_eq!(vec_minmax(v.as_ptr(), 4, &mut mn, &mut mx), 0);
        assert!((mn + 3.0).abs() < 1e-9);
        assert!((mx - 5.0).abs() < 1e-9);
    }
    #[test]
    fn corr_neg() {
        let a = [1.0, 2.0, 3.0, 4.0, 5.0];
        let b = [5.0, 4.0, 3.0, 2.0, 1.0];
        let c = vec_correlation(a.as_ptr(), b.as_ptr(), 5);
        assert!((c + 1.0).abs() < 1e-9);
    }
    #[test]
    fn mat_mul_square() {
        let a = [1.0, 2.0, 3.0, 4.0];
        let b = [5.0, 6.0, 7.0, 8.0];
        let mut out = [0.0f64; 4];
        assert_eq!(
            mat_mul(a.as_ptr(), 2, 2, b.as_ptr(), 2, 2, out.as_mut_ptr()),
            0
        );
        assert!((out[0] - 19.0).abs() < 1e-9);
        assert!((out[3] - 50.0).abs() < 1e-9);
    }
}
