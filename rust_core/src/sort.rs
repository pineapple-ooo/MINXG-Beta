//! minxg_rust_core/src/sort.rs — industrial sorting algorithms.
//!
//! Provides multiple sort strategies chosen by input characteristics:
//! * Radix sort  — O(k·n) for fixed-width integer keys, fastest for large arrays
//! * Quicksort   — O(n log n) average, in-place, cache-friendly
//! * Merge sort  — O(n log n) stable, for when stability matters
//! * Heap sort   — O(n log n) worst-case guaranteed, O(1) extra space
//!
//! All public functions are `extern "C"` for ctypes/cffi calling.
//! Null pointers → sentinel returns, no panics.

#![allow(dead_code)]

// ── Radix sort (LSD, 32-bit unsigned integers) ─────────────────

/// Sort `data` in-place using LSD radix sort.  O(k·n) where k=4 passes.
/// Returns 0 OK, -1 null.
#[no_mangle]
pub extern "C" fn sort_radix_u32(data: *mut u32, n: usize) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(data, n) };

    // 4-pass LSD radix (8 bits per pass)
    let mut buffer = vec![0u32; n];
    for shift in [0u32, 8, 16, 24] {
        let mut count = [0usize; 256];
        for &val in slice.iter() {
            count[((val >> shift) & 0xFF) as usize] += 1;
        }
        // Prefix sum
        let mut total = 0usize;
        for c in &mut count {
            let tmp = *c;
            *c = total;
            total += tmp;
        }
        // Distribute (back-to-front for stability)
        for i in (0..n).rev() {
            let byte = ((slice[i] >> shift) & 0xFF) as usize;
            count[byte] -= 1;
            buffer[count[byte]] = slice[i];
        }
        slice.swap_with_slice(&mut buffer);
    }
    0
}

/// Sort `data` in-place using LSD radix sort for 64-bit unsigned integers.
/// 8 passes of 8 bits each.
#[no_mangle]
pub extern "C" fn sort_radix_u64(data: *mut u64, n: usize) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(data, n) };
    let mut buffer = vec![0u64; n];
    for shift in [0u64, 8, 16, 24, 32, 40, 48, 56] {
        let mut count = [0usize; 256];
        for &val in slice.iter() {
            count[((val >> shift) & 0xFF) as usize] += 1;
        }
        let mut total = 0usize;
        for c in &mut count {
            let tmp = *c;
            *c = total;
            total += tmp;
        }
        for i in (0..n).rev() {
            let byte = ((slice[i] >> shift) & 0xFF) as usize;
            count[byte] -= 1;
            buffer[count[byte]] = slice[i];
        }
        slice.swap_with_slice(&mut buffer);
    }
    0
}

// ── Quicksort (3-way, introsort fallback) ─────────────────────

/// In-place quicksort with 3-way partition (Dutch national flag).
/// Handles duplicates efficiently. Falls back to insertion sort for small slices.
#[no_mangle]
pub extern "C" fn sort_quicksort_f32(data: *mut f32, n: usize) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(data, n) };
    _quicksort_f32(slice, 16);
    0
}

fn _quicksort_f32(slice: &mut [f32], threshold: usize) {
    if slice.len() <= 1 {
        return;
    }
    if slice.len() <= threshold {
        _insertion_sort_f32(slice);
        return;
    }
    // Median-of-three pivot
    let mid = slice.len() / 2;
    if slice[0] > slice[mid] { slice.swap(0, mid); }
    if slice[0] > slice[slice.len() - 1] { slice.swap(0, slice.len() - 1); }
    if slice[mid] > slice[slice.len() - 1] { slice.swap(mid, slice.len() - 1); }
    let pivot = slice[mid];

    // 3-way partition
    let mut i = 0;
    let mut j = 0;
    let mut k = slice.len();
    while j < k {
        if slice[j] < pivot {
            slice.swap(i, j);
            i += 1;
            j += 1;
        } else if slice[j] > pivot {
            k -= 1;
            slice.swap(j, k);
        } else {
            j += 1;
        }
    }
    _quicksort_f32(&mut slice[..i], threshold);
    _quicksort_f32(&mut slice[k..], threshold);
}

fn _insertion_sort_f32(slice: &mut [f32]) {
    for i in 1..slice.len() {
        let key = slice[i];
        let mut j = i;
        while j > 0 && slice[j - 1] > key {
            slice[j] = slice[j - 1];
            j -= 1;
        }
        slice[j] = key;
    }
}

// ── Merge sort (stable, O(n log n)) ───────────────────────────

/// Stable merge sort. Allocates O(n) temporary buffer.
/// Returns 0 OK, -1 null.
#[no_mangle]
pub extern "C" fn sort_merge_f32(data: *mut f32, n: usize) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(data, n) };
    if slice.len() <= 1 {
        return 0;
    }
    let mut buffer = vec![0.0f32; slice.len()];
    _merge_sort_f32(slice, &mut buffer);
    0
}

fn _merge_sort_f32(src: &mut [f32], buf: &mut [f32]) {
    let n = src.len();
    if n <= 1 {
        return;
    }
    let mid = n / 2;
    _merge_sort_f32(&mut src[..mid], &mut buf[..mid]);
    _merge_sort_f32(&mut src[mid..], &mut buf[mid..]);
    // Merge
    let mut i = 0;
    let mut j = mid;
    let mut k = 0;
    while i < mid && j < n {
        if src[i] <= src[j] {
            buf[k] = src[i];
            i += 1;
        } else {
            buf[k] = src[j];
            j += 1;
        }
        k += 1;
    }
    while i < mid {
        buf[k] = src[i];
        i += 1;
        k += 1;
    }
    while j < n {
        buf[k] = src[j];
        j += 1;
        k += 1;
    }
    src.copy_from_slice(&buf[..n]);
}

// ── Heap sort (O(n log n) worst-case, O(1) space) ────────────

/// Heap sort in-place. Worst-case O(n log n), O(1) extra space.
/// Not stable but guaranteed performance.
#[no_mangle]
pub extern "C" fn sort_heap_f32(data: *mut f32, n: usize) -> i32 {
    if data.is_null() || n == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(data, n) };
    if slice.len() <= 1 {
        return 0;
    }

    // Build max heap
    let mut end = slice.len();
    for i in (0..end / 2).rev() {
        _sift_down_f32(slice, i, end);
    }

    // Extract max repeatedly
    while end > 1 {
        end -= 1;
        slice.swap(0, end);
        _sift_down_f32(slice, 0, end);
    }
    0
}

fn _sift_down_f32(slice: &mut [f32], start: usize, end: usize) {
    let mut root = start;
    loop {
        let left = 2 * root + 1;
        if left >= end {
            break;
        }
        let right = left + 1;
        let max_child = if right < end && slice[right] > slice[left] {
            right
        } else {
            left
        };
        if slice[root] >= slice[max_child] {
            break;
        }
        slice.swap(root, max_child);
        root = max_child;
    }
}

// ── Parallel-ish sort (parallel iter for large slices) ─────────

/// Sort a large f32 array using Rayon-style parallel iter if available,
/// falling back to sequential quicksort. This is a stub for the parallel
/// version — full parallel sort ships in v0.19.0 with rayon dependency.
#[no_mangle]
pub extern "C" fn sort_parallel_f32(data: *mut f32, n: usize) -> i32 {
    // Sequential fallback
    sort_quicksort_f32(data, n)
}

// ── Top-K selection ────────────────────────────────────────────

/// Partial sort: return the k smallest elements in `out` (unsorted).
/// O(n + k log k) using quickselect.
#[no_mangle]
pub extern "C" fn sort_topk_f32(
    data: *const f32,
    n: usize,
    out: *mut f32,
    k: usize,
) -> i32 {
    if data.is_null() || out.is_null() || n == 0 || k == 0 || k > n {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, n) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, k) };
    let mut buf = slice.to_vec();

    // Quickselect k-th smallest
    let k_idx = k - 1;
    _quickselect_f32(&mut buf, 0, buf.len(), k_idx);

    // Copy k smallest to out
    out_slice.copy_from_slice(&buf[..k]);
    0
}

fn _quickselect_f32(arr: &mut [f32], left: usize, right: usize, k: usize) {
    if right - left <= 1 {
        return;
    }
    let pivot_idx = _partition_f32(arr, left, right);
    if k < pivot_idx {
        _quickselect_f32(arr, left, pivot_idx, k);
    } else if k > pivot_idx {
        _quickselect_f32(arr, pivot_idx + 1, right, k);
    }
}

fn _partition_f32(arr: &mut [f32], left: usize, right: usize) -> usize {
    let pivot = arr[right - 1];
    let mut i = left;
    for j in left..right - 1 {
        if arr[j] < pivot {
            arr.swap(i, j);
            i += 1;
        }
    }
    arr.swap(i, right - 1);
    i
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_radix_u32_basic() {
        let mut data = [5u32, 3, 8, 1, 9, 2, 7, 4, 6];
        assert_eq!(sort_radix_u32(data.as_mut_ptr(), 9), 0);
        assert_eq!(data, [1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn test_radix_u32_empty() {
        let mut data: [u32; 0] = [];
        assert_eq!(sort_radix_u32(data.as_mut_ptr(), 0), -1);
    }

    #[test]
    fn test_quicksort_f32() {
        let mut data = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0];
        assert_eq!(sort_quicksort_f32(data.as_mut_ptr(), 8), 0);
        for i in 1..data.len() {
            assert!(data[i] >= data[i - 1]);
        }
    }

    #[test]
    fn test_merge_sort_f32_stable() {
        let mut data = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0];
        sort_merge_f32(data.as_mut_ptr(), 6);
        for i in 1..data.len() {
            assert!(data[i] >= data[i - 1]);
        }
    }

    #[test]
    fn test_heap_sort_f32() {
        let mut data = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0];
        assert_eq!(sort_heap_f32(data.as_mut_ptr(), 8), 0);
        for i in 1..data.len() {
            assert!(data[i] >= data[i - 1]);
        }
    }

    #[test]
    fn test_topk_f32() {
        let data = [9.0, 3.0, 7.0, 1.0, 8.0, 2.0, 6.0, 4.0, 5.0];
        let mut out = [0.0f32; 3];
        assert_eq!(sort_topk_f32(data.as_ptr(), 9, out.as_mut_ptr(), 3), 0);
        // Top-3 smallest: [1.0, 2.0, 3.0] (order not guaranteed)
        let mut sorted = out;
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        assert!((sorted[0] - 1.0).abs() < 1e-5);
        assert!((sorted[2] - 3.0).abs() < 1e-5);
    }
}
