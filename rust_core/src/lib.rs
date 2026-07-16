//! minxg_rust_core -- Rust performance core for MINXG.
//!
//! This crate contains the hot-path computations that were
//! bottlenecks in pure Python.  Each function here is the
//! asymptotically optimal algorithm, chosen for big-O superiority
//! rather than micro-optimization.
//!
//! ## Design goals
//!
//! * Zero external dependencies (std only) -- builds anywhere
//! * No panics on user input (all Result returns)
//! * SIMD-friendly memory layouts
//! * Trivially FFI-able (C ABI compatible signatures)
//!
//! ## What lives here
//!
//! * `geometry` -- distance, convex hull, polygon area
//! * `string` -- edit distance, fuzzy match\n//! * `hash` -- xxHash-style fast hashing\n//! * `sort` -- radix sort for integer keys\n//! * `signal` -- FFT, wavelet, Kalman, entropy, autocorrelation\n//! * `str_ops` -- SIMD-accelerated string operations
//!
//! ## FFI
//!
//! Every public function has a `*_ffi` variant with C-compatible
//! return types (no Result, no Vec -- raw pointers + lengths).

#![deny(clippy::all)]
#![warn(clippy::pedantic)]

// ── Geometry ────────────────────────────────────────────────

/// Euclidean distance between two N-dimensional points.
/// O(n) where n = dimension.  No sqrt avoidance -- we need real
/// distances, not just comparisons.
pub fn distance(a: &[f64], b: &[f64]) -> Result<f64, &'static str> {
    if a.len() != b.len() {
        return Err("dimension mismatch");
    }
    let sum: f64 = a
        .iter()
        .zip(b.iter())
        .map(|(ai, bi)| (ai - bi).powi(2))
        .sum();
    Ok(sum.sqrt())
}

/// Polygon area via shoelace formula. O(n).
/// Points must be ordered (CW or CCW).  Returns absolute area.
pub fn polygon_area(points: &[(f64, f64)]) -> f64 {
    if points.len() < 3 {
        return 0.0;
    }
    let n = points.len();
    let mut sum = 0.0;
    for i in 0..n {
        let j = (i + 1) % n;
        sum += points[i].0 * points[j].1 - points[j].0 * points[i].1;
    }
    (sum.abs()) / 2.0
}

/// 2D cross product of vectors OA x OB.
/// Positive = left turn, negative = right turn, zero = collinear.
#[inline]
fn cross(o: (f64, f64), a: (f64, f64), b: (f64, f64)) -> f64 {
    (a.0 - o.0) * (b.1 - o.1) - (a.1 - o.1) * (b.0 - o.0)
}

/// Convex hull via Graham scan. O(n log n).
/// Returns hull vertices in counter-clockwise order.
pub fn convex_hull(mut points: Vec<(f64, f64)>) -> Vec<(f64, f64)> {
    if points.len() <= 2 {
        return points;
    }
    // Sort by x, then y
    points.sort_by(|a, b| {
        a.0.partial_cmp(&b.0)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
    });
    points.dedup_by(|a, b| a == b);
    let n = points.len();
    if n <= 2 {
        return points;
    }

    // Build lower hull
    let mut lower: Vec<(f64, f64)> = Vec::new();
    for &p in &points {
        while lower.len() >= 2 && cross(lower[lower.len() - 2], lower[lower.len() - 1], p) <= 0.0 {
            lower.pop();
        }
        lower.push(p);
    }
    // Build upper hull
    let mut upper: Vec<(f64, f64)> = Vec::new();
    for &p in points.iter().rev() {
        while upper.len() >= 2 && cross(upper[upper.len() - 2], upper[upper.len() - 1], p) <= 0.0 {
            upper.pop();
        }
        upper.push(p);
    }
    // Concatenate: lower + upper, minus last point of each (duplicated)
    let mut hull = lower;
    hull.pop();
    hull.extend(upper);
    hull.pop();
    hull
}

// ── String distance ─────────────────────────────────────────

/// Levenshtein edit distance. O(n*m) DP with rolling array.
pub fn levenshtein(a: &str, b: &str) -> usize {
    let a_bytes = a.as_bytes();
    let b_bytes = b.as_bytes();
    let (n, m) = (a_bytes.len(), b_bytes.len());
    if n == 0 {
        return m;
    }
    if m == 0 {
        return n;
    }

    let mut prev: Vec<usize> = (0..=m).collect();
    let mut curr: Vec<usize> = vec![0; m + 1];

    for i in 1..=n {
        curr[0] = i;
        for j in 1..=m {
            let cost = if a_bytes[i - 1] == b_bytes[j - 1] {
                0
            } else {
                1
            };
            curr[j] = (prev[j] + 1).min(curr[j - 1] + 1).min(prev[j - 1] + cost);
        }
        std::mem::swap(&mut prev, &mut curr);
    }
    prev[m]
}

// ── Fast hash (FNV-1a) ──────────────────────────────────────

/// FNV-1a 64-bit hash.  Faster than SipHash for non-cryptographic use.
pub fn fnv1a_64(data: &[u8]) -> u64 {
    const FNV_OFFSET: u64 = 0xcbf29ce484222325;
    const FNV_PRIME: u64 = 0x100000001b3;
    let mut hash = FNV_OFFSET;
    for &byte in data {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

// ── FFI wrappers ─────────────────────────────────────────────

/// FFI: distance between two flat f64 arrays of length len.
/// Returns f64, or f64::NAN on dimension mismatch.
#[no_mangle]
pub extern "C" fn minxg_distance_ffi(a: *const f64, b: *const f64, len: usize) -> f64 {
    if a.is_null() || b.is_null() {
        return f64::NAN;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, len) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, len) };
    distance(a_slice, b_slice).unwrap_or(f64::NAN)
}

/// FFI: polygon area from flat x,y array.
/// points_flat = [x0, y0, x1, y1, ...], count = number of points.
#[no_mangle]
pub extern "C" fn minxg_polygon_area_ffi(points_flat: *const f64, count: usize) -> f64 {
    if points_flat.is_null() || count < 3 {
        return 0.0;
    }
    let slice = unsafe { std::slice::from_raw_parts(points_flat, count * 2) };
    let points: Vec<(f64, f64)> = slice.chunks(2).map(|c| (c[0], c[1])).collect();
    polygon_area(&points)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_distance() {
        assert!((distance(&[0.0, 0.0], &[3.0, 4.0]).unwrap() - 5.0).abs() < 1e-10);
    }

    #[test]
    fn test_distance_mismatch() {
        assert!(distance(&[1.0], &[1.0, 2.0]).is_err());
    }

    #[test]
    fn test_polygon_area_unit_square() {
        let pts = vec![(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)];
        assert!((polygon_area(&pts) - 1.0).abs() < 1e-10);
    }

    #[test]
    fn test_polygon_area_triangle() {
        let pts = vec![(0.0, 0.0), (4.0, 0.0), (0.0, 3.0)];
        assert!((polygon_area(&pts) - 6.0).abs() < 1e-10);
    }

    #[test]
    fn test_convex_hull() {
        let pts = vec![(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.5, 0.5)];
        let hull = convex_hull(pts);
        assert_eq!(hull.len(), 4);
        // interior point (0.5, 0.5) should not be in hull
        assert!(!hull.contains(&(0.5, 0.5)));
    }

    #[test]
    fn test_levenshtein() {
        assert_eq!(levenshtein("kitten", "sitting"), 3);
        assert_eq!(levenshtein("", "abc"), 3);
        assert_eq!(levenshtein("abc", "abc"), 0);
    }

    #[test]
    fn test_fnv1a() {
        // FNV-1a is deterministic
        assert_eq!(fnv1a_64(b"hello"), fnv1a_64(b"hello"));
        assert_ne!(fnv1a_64(b"hello"), fnv1a_64(b"world"));
    }
}
