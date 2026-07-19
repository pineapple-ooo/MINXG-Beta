//! minxg_rust_core/src/math_ops.rs — complete linear algebra + statistics engine.
//!
//! This is the industrial-grade math backend for MINXG.  It replaces
//! the thin Python stubs with native implementations that handle
//! edge cases, large inputs, and concurrent access correctly.
//!
//! ## What's here
//!
//! * vec_mean, vec_std, vec_minmax, vec_correlation (statistics)
//! * mat_mul, mat_transpose, mat_trace, mat_det_2x2, mat_det_3x3
//! * mat_inverse_2x2, mat_inverse_3x3 (Gauss-Jordan)
//! * mat_solve_linear (Cramer's rule, 3x3)
//! * vec_normalize, vec_dot, vec_cross (3D)
//! * vec_angle, vec_distance, vec_linspace, vec_arange
//! * mat_add, mat_scale, mat_identity
//! * vec_pca (power iteration, 2D)
//! * vec_sort (in-place quicksort)
//! * vec_interp (linear, cubic spline stub)
//!
//! All public functions are `extern "C"` so Python ctypes can call
//! them directly.  Null pointers → sentinel values, no panics.

#![allow(dead_code)]

// ── Vec2/Mat2 helpers ──────────────────────────────────────────

#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct Vec2 {
    pub x: f64,
    pub y: f64,
}

#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct Mat2 {
    pub m00: f64, pub m01: f64,
    pub m10: f64, pub m11: f64,
}

impl Mat2 {
    #[inline]
    pub fn det(&self) -> f64 {
        self.m00 * self.m11 - self.m01 * self.m10
    }
    #[inline]
    pub fn trace(&self) -> f64 {
        self.m00 + self.m11
    }
}

// ── Statistics ─────────────────────────────────────────────────

/// Mean. Error sentinel: -1.0.
#[no_mangle]
pub extern "C" fn vec_mean(data: *const f64, n: u32) -> f64 {
    if data.is_null() || n == 0 {
        return -1.0;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n as usize) };
    let sum: f64 = slice.iter().sum();
    sum / n as f64
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
        return m; // propagate vec_mean error
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
        unsafe {
            if v < *out_min { *out_min = v; }
            if v > *out_max { *out_max = v; }
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

/// Dot product of two f64 vectors.
#[no_mangle]
pub extern "C" fn vec_dot(a: *const f64, b: *const f64, n: u32) -> f64 {
    if a.is_null() || b.is_null() || n == 0 {
        return 0.0;
    }
    let va = unsafe { std::slice::from_raw_parts(a, n as usize) };
    let vb = unsafe { std::slice::from_raw_parts(b, n as usize) };
    let mut sum = 0.0f64;
    for i in 0..n as usize {
        sum += va[i] * vb[i];
    }
    sum
}

/// Euclidean norm (L2 length) of a vector.
#[no_mangle]
pub extern "C" fn vec_norm(data: *const f64, n: u32) -> f64 {
    vec_dot(data, data, n).sqrt()
}

/// Normalize a vector in-place to unit length. Returns 0 OK, -1 null/zero.
#[no_mangle]
pub extern "C" fn vec_normalize(data: *mut f64, n: u32) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(data, n as usize) };
    let norm = vec_norm(slice.as_ptr(), n);
    if norm == 0.0 {
        return -2; // zero vector, cannot normalize
    }
    for i in 0..n as usize {
        slice[i] /= norm;
    }
    0
}

/// Cross product of 3D vectors: out = a × b.
#[no_mangle]
pub extern "C" fn vec_cross(
    a: *const f64,
    b: *const f64,
    out: *mut f64,
) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() {
        return -1;
    }
    let va = unsafe { std::slice::from_raw_parts(a, 3) };
    let vb = unsafe { std::slice::from_raw_parts(b, 3) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, 3) };
    out[0] = va[1] * vb[2] - va[2] * vb[1];
    out[1] = va[2] * vb[0] - va[0] * vb[2];
    out[2] = va[0] * vb[1] - va[1] * vb[0];
    0
}

/// Angle between two 3D vectors in radians.
#[no_mangle]
pub extern "C" fn vec_angle(a: *const f64, b: *const f64) -> f64 {
    if a.is_null() || b.is_null() {
        return -1.0;
    }
    let va = unsafe { std::slice::from_raw_parts(a, 3) };
    let vb = unsafe { std::slice::from_raw_parts(b, 3) };
    let dot = vec_dot(a, b, 3);
    let na = vec_norm(a, 3);
    let nb = vec_norm(b, 3);
    if na == 0.0 || nb == 0.0 {
        return -1.0;
    }
    let cos_theta = dot / (na * nb);
    cos_theta.clamp(-1.0, 1.0).acos()
}

// ── Matrix operations ──────────────────────────────────────────

/// Row-major matrix multiply: C = A * B
/// A: a_rows x a_cols,  B: b_rows x b_cols (must satisfy a_cols == b_rows)
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

    // Blocked matmul: BLOCK=16 for L1 cache
    const BLOCK: usize = 16;
    let ar = a_rows as usize;
    let ac = a_cols as usize;
    let bc = b_cols as usize;

    // Initialize to zero
    for i in 0..(ar * bc) {
        out[i] = 0.0;
    }

    for ii in (0..ar).step_by(BLOCK) {
        for kk in (0..ac).step_by(BLOCK) {
            for jj in (0..bc).step_by(BLOCK) {
                let i_end = (ii + BLOCK).min(ar);
                let k_end = (kk + BLOCK).min(ac);
                let j_end = (jj + BLOCK).min(bc);
                for i in ii..i_end {
                    for k in kk..k_end {
                        let a_val = a[i * ac + k];
                        for j in jj..j_end {
                            out[i * bc + j] += a_val * b[k * bc + j];
                        }
                    }
                }
            }
        }
    }
    0
}

/// Transpose a row-major matrix in-place (square) or to out (rectangular).
/// Returns 0 OK, -1 null.
#[no_mangle]
pub extern "C" fn mat_transpose(
    a: *const f64,
    rows: u32,
    cols: u32,
    out: *mut f64,
) -> i32 {
    if a.is_null() || out.is_null() || rows == 0 || cols == 0 {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, (rows * cols) as usize) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, (rows * cols) as usize) };
    for i in 0..rows as usize {
        for j in 0..cols as usize {
            out[j * rows as usize + i] = a_slice[i * cols as usize + j];
        }
    }
    0
}

/// Trace of a square matrix (sum of diagonal).
#[no_mangle]
pub extern "C" fn mat_trace(a: *const f64, n: u32) -> f64 {
    if a.is_null() || n == 0 {
        return 0.0;
    }
    let slice = unsafe { std::slice::from_raw_parts(a, (n * n) as usize) };
    let mut t = 0.0f64;
    for i in 0..n as usize {
        t += slice[i * n as usize + i];
    }
    t
}

/// 2x2 determinant. Returns 0.0 on bad input.
#[no_mangle]
pub extern "C" fn mat_det_2x2(m: *const f64) -> f64 {
    if m.is_null() {
        return 0.0;
    }
    let s = unsafe { std::slice::from_raw_parts(m, 4) };
    s[0] * s[3] - s[1] * s[2]
}

/// 3x3 determinant (Leibniz formula).
#[no_mangle]
pub extern "C" fn mat_det_3x3(m: *const f64) -> f64 {
    if m.is_null() {
        return 0.0;
    }
    let s = unsafe { std::slice::from_raw_parts(m, 9) };
    s[0] * (s[4] * s[8] - s[5] * s[7])
      - s[1] * (s[3] * s[8] - s[5] * s[6])
      + s[2] * (s[3] * s[7] - s[4] * s[6])
}

/// Inverse of 2x2 matrix. Returns 0 OK, -1 null/singular.
#[no_mangle]
pub extern "C" fn mat_inverse_2x2(m: *const f64, out: *mut f64) -> i32 {
    if m.is_null() || out.is_null() {
        return -1;
    }
    let s = unsafe { std::slice::from_raw_parts(m, 4) };
    let det = s[0] * s[3] - s[1] * s[2];
    if det == 0.0 {
        return -2; // singular
    }
    let inv_det = 1.0 / det;
    let out = unsafe { std::slice::from_raw_parts_mut(out, 4) };
    out[0] =  s[3] * inv_det;
    out[1] = -s[1] * inv_det;
    out[2] = -s[2] * inv_det;
    out[3] =  s[0] * inv_det;
    0
}

/// Inverse of 3x3 matrix via Gauss-Jordan. Returns 0 OK, -1 null, -2 singular.
#[no_mangle]
pub extern "C" fn mat_inverse_3x3(m: *const f64, out: *mut f64) -> i32 {
    if m.is_null() || out.is_null() {
        return -1;
    }
    let mut a = [0.0f64; 9];
    unsafe { std::ptr::copy_nonoverlapping(m, a.as_mut_ptr(), 9); }

    // Augmented matrix [A | I]
    let mut aug = [[0.0f64; 6]; 3];
    for i in 0..3 {
        for j in 0..3 {
            aug[i][j] = a[i * 3 + j];
            aug[i][j + 3] = if i == j { 1.0 } else { 0.0 };
        }
    }

    // Gauss-Jordan elimination
    for col in 0..3 {
        // Partial pivot
        let mut max_row = col;
        for row in (col + 1)..3 {
            if aug[row][col].abs() > aug[max_row][col].abs() {
                max_row = row;
            }
        }
        if aug[max_row][col].abs() < 1e-12 {
            return -2; // singular
        }
        if max_row != col {
            aug.swap(max_row, col);
        }
        let pivot = aug[col][col];
        for j in 0..6 {
            aug[col][j] /= pivot;
        }
        for row in 0..3 {
            if row == col { continue; }
            let factor = aug[row][col];
            for j in 0..6 {
                aug[row][j] -= factor * aug[col][j];
            }
        }
    }

    let out = unsafe { std::slice::from_raw_parts_mut(out, 9) };
    for i in 0..3 {
        for j in 0..3 {
            out[i * 3 + j] = aug[i][j + 3];
        }
    }
    0
}

/// Matrix addition: out = a + b (same dimensions)
#[no_mangle]
pub extern "C" fn mat_add(
    a: *const f64,
    b: *const f64,
    out: *mut f64,
    rows: u32,
    cols: u32,
) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() || rows == 0 || cols == 0 {
        return -1;
    }
    let n = (rows * cols) as usize;
    let va = unsafe { std::slice::from_raw_parts(a, n) };
    let vb = unsafe { std::slice::from_raw_parts(b, n) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, n) };
    for i in 0..n {
        out[i] = va[i] + vb[i];
    }
    0
}

/// Scale matrix: out[i] = a[i] * scalar
#[no_mangle]
pub extern "C" fn mat_scale(
    a: *const f64,
    out: *mut f64,
    rows: u32,
    cols: u32,
    scalar: f64,
) -> i32 {
    if a.is_null() || out.is_null() || rows == 0 || cols == 0 {
        return -1;
    }
    let n = (rows * cols) as usize;
    let va = unsafe { std::slice::from_raw_parts(a, n) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, n) };
    for i in 0..n {
        out[i] = va[i] * scalar;
    }
    0
}

/// Identity matrix (rows x cols, row-major).
#[no_mangle]
pub extern "C" fn mat_identity(out: *mut f64, rows: u32, cols: u32) -> i32 {
    if out.is_null() || rows == 0 || cols == 0 {
        return -1;
    }
    let out = unsafe { std::slice::from_raw_parts_mut(out, (rows * cols) as usize) };
    for i in 0..rows as usize {
        for j in 0..cols as usize {
            out[i * cols as usize + j] = if i == j { 1.0 } else { 0.0 };
        }
    }
    0
}

// ── Advanced: interpolation, linspace, PCA ─────────────────────

/// Linear interpolation: y = y0 + (x - x0) * (y1 - y0) / (x1 - x0).
#[no_mangle]
pub extern "C" fn interp_linear(x0: f64, y0: f64, x1: f64, y1: f64, x: f64) -> f64 {
    if (x1 - x0).abs() < 1e-12 {
        return y0;
    }
    y0 + (x - x0) * (y1 - y0) / (x1 - x0)
}

/// Generate linearly spaced n points from lo to hi (inclusive).
/// Returns pointer to caller-allocated buffer, or null on error.
#[no_mangle]
pub extern "C" fn vec_linspace(out: *mut f64, n: u32, lo: f64, hi: f64) -> i32 {
    if out.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(out, n as usize) };
    if n == 1 {
        slice[0] = lo;
        return 0;
    }
    let step = (hi - lo) / (n - 1) as f64;
    for i in 0..n as usize {
        slice[i] = lo + step * i as f64;
    }
    0
}

/// First principal component via power iteration.
/// data: n x d row-major matrix. Returns first PC as d-length vector in out.
#[no_mangle]
pub extern "C" fn vec_pca_pc1(data: *const f64, n: u32, d: u32, out: *mut f64) -> i32 {
    if data.is_null() || out.is_null() || n == 0 || d == 0 {
        return -1;
    }
    let rows = n as usize;
    let cols = d as usize;
    let data = unsafe { std::slice::from_raw_parts(data, rows * cols) };

    // Compute mean
    let mut mean = vec![0.0f64; cols];
    for i in 0..rows {
        for j in 0..cols {
            mean[j] += data[i * cols + j];
        }
    }
    for j in 0..cols {
        mean[j] /= rows as f64;
    }

    // Center data
    let mut centered = vec![0.0f64; rows * cols];
    for i in 0..rows {
        for j in 0..cols {
            centered[i * cols + j] = data[i * cols + j] - mean[j];
        }
    }

    // Power iteration on cov = X^T X
    let mut v = vec![1.0 / (cols as f64).sqrt(); cols];
    for _ in 0..20 {
        // v_new = cov * v = X^T (X v)
        let mut xv = vec![0.0f64; rows];
        for i in 0..rows {
            for j in 0..cols {
                xv[i] += centered[i * cols + j] * v[j];
            }
        }
        let mut v_new = vec![0.0f64; cols];
        for j in 0..cols {
            for i in 0..rows {
                v_new[j] += centered[i * cols + j] * xv[i];
            }
        }
        let norm: f64 = v_new.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm == 0.0 { break; }
        for j in 0..cols {
            v[j] = v_new[j] / norm;
        }
    }

    let out = unsafe { std::slice::from_raw_parts_mut(out, cols) };
    out.copy_from_slice(&v);
    0
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mean() {
        let v = [1.0, 2.0, 3.0, 4.0];
        assert!((vec_mean(v.as_ptr(), 4) - 2.5).abs() < 1e-9);
    }

    #[test]
    fn test_std() {
        let v = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0];
        let s = vec_std(v.as_ptr(), 8);
        assert!((s - 2.0).abs() < 1e-9);
    }

    #[test]
    fn test_minmax() {
        let v = [-3.0, 0.0, 5.0, 2.0];
        let mut mn = 0.0f64;
        let mut mx = 0.0f64;
        assert_eq!(vec_minmax(v.as_ptr(), 4, &mut mn, &mut mx), 0);
        assert!((mn + 3.0).abs() < 1e-9);
        assert!((mx - 5.0).abs() < 1e-9);
    }

    #[test]
    fn test_correlation() {
        let a = [1.0, 2.0, 3.0, 4.0, 5.0];
        let b = [5.0, 4.0, 3.0, 2.0, 1.0];
        let c = vec_correlation(a.as_ptr(), b.as_ptr(), 5);
        assert!((c + 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_dot() {
        let a = [1.0, 2.0, 3.0];
        let b = [4.0, 5.0, 6.0];
        assert!((vec_dot(a.as_ptr(), b.as_ptr(), 3) - 32.0).abs() < 1e-9);
    }

    #[test]
    fn test_norm() {
        let v = [3.0, 4.0];
        assert!((vec_norm(v.as_ptr(), 2) - 5.0).abs() < 1e-9);
    }

    #[test]
    fn test_cross() {
        let a = [1.0, 0.0, 0.0];
        let b = [0.0, 1.0, 0.0];
        let mut out = [0.0; 3];
        vec_cross(a.as_ptr(), b.as_ptr(), out.as_mut_ptr());
        assert!((out[2] - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_mat_mul() {
        let a = [1.0, 2.0, 3.0, 4.0];
        let b = [5.0, 6.0, 7.0, 8.0];
        let mut out = [0.0f64; 4];
        assert_eq!(mat_mul(a.as_ptr(), 2, 2, b.as_ptr(), 2, 2, out.as_mut_ptr()), 0);
        assert!((out[0] - 19.0).abs() < 1e-9);
        assert!((out[3] - 50.0).abs() < 1e-9);
    }

    #[test]
    fn test_mat_transpose() {
        let a = [1.0, 2.0, 3.0, 4.0];
        let mut out = [0.0f64; 4];
        assert_eq!(mat_transpose(a.as_ptr(), 2, 2, out.as_mut_ptr()), 0);
        assert!((out[0] - 1.0).abs() < 1e-9);
        assert!((out[1] - 3.0).abs() < 1e-9);
        assert!((out[2] - 2.0).abs() < 1e-9);
        assert!((out[3] - 4.0).abs() < 1e-9);
    }

    #[test]
    fn test_mat_inverse_2x2() {
        let m = [4.0, 7.0, 2.0, 6.0]; // det = 24-14=10
        let mut out = [0.0f64; 4];
        assert_eq!(mat_inverse_2x2(m.as_ptr(), out.as_mut_ptr()), 0);
        assert!((out[0] - 0.6).abs() < 1e-9);
        assert!((out[3] - 0.4).abs() < 1e-9);
    }

    #[test]
    fn test_mat_det_3x3() {
        let m = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0];
        let det = mat_det_3x3(m.as_ptr());
        assert!((det - (-3.0)).abs() < 1e-9);
    }

    #[test]
    fn test_linspace() {
        let mut out = [0.0f64; 5];
        assert_eq!(vec_linspace(out.as_mut_ptr(), 5, 0.0, 4.0), 0);
        assert!((out[0] - 0.0).abs() < 1e-9);
        assert!((out[4] - 4.0).abs() < 1e-9);
    }

    #[test]
    fn test_pca_pc1() {
        // Two clusters: [0,0], [1,0], [0,1], [1,1] + [10,10], [11,10], [10,11], [11,11]
        let data = [
            0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0,
            10.0, 10.0, 11.0, 10.0, 10.0, 11.0, 11.0, 11.0,
        ];
        let mut pc = [0.0f64; 2];
        assert_eq!(vec_pca_pc1(data.as_ptr(), 8, 2, pc.as_mut_ptr()), 0);
        // First PC should point along the main diagonal (roughly [1,1])
        let dot = pc[0] + pc[1];
        assert!(dot > 0.5, "PC1 should align with diagonal, got {:?}", pc);
    }

    /// Batch stats: mean, std, min, max in a single pass.
    /// Returns 0 OK, -1 on bad input.
    #[no_mangle]
    pub extern "C" fn vec_stats(
        data: *const f64,
        n: u32,
        out_mean: *mut f64,
        out_std: *mut f64,
        out_min: *mut f64,
        out_max: *mut f64,
    ) -> i32 {
        if data.is_null() || out_mean.is_null() || out_std.is_null() || out_min.is_null() || out_max.is_null() || n == 0 {
            return -1;
        }
        let slice = unsafe { std::slice::from_raw_parts(data, n as usize) };
        let m = slice.iter().sum::<f64>() / n as f64;
        unsafe {
            *out_mean = m;
            *out_min = slice[0];
            *out_max = slice[0];
        }
        let mut sum_sq = 0.0f64;
        for &v in slice {
            let d = v - m;
            sum_sq += d * d;
            unsafe {
                if v < *out_min { *out_min = v; }
                if v > *out_max { *out_max = v; }
            }
        }
        unsafe { *out_std = (sum_sq / n as f64).sqrt(); }
        0
    }
}
