// Rust Bridge for MINXG
// Compile with: rustc --crate-type=cdylib -o librust_bridge.so rust_bridge.rs

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::{Arc, Mutex};

// Matrix operations
pub fn matrix_multiply(a: &[Vec<f64>], b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let n = a.len();
    let m = a[0].len();
    let p = b[0].len();
    let mut result = vec![vec![0.0; p]; n];

    for i in 0..n {
        for j in 0..p {
            for k in 0..m {
                result[i][j] += a[i][k] * b[k][j];
            }
        }
    }
    result
}

pub fn matrix_transpose(m: &[Vec<f64>]) -> Vec<Vec<f64>> {
    if m.is_empty() { return vec![]; }
    let rows = m.len();
    let cols = m[0].len();
    let mut result = vec![vec![0.0; rows]; cols];
    for i in 0..rows {
        for j in 0..cols {
            result[j][i] = m[i][j];
        }
    }
    result
}

pub fn matrix_determinant(m: &[Vec<f64>]) -> f64 {
    let n = m.len();
    if n == 1 { return m[0][0]; }
    if n == 2 { return m[0][0] * m[1][1] - m[0][1] * m[1][0]; }

    let mut det = 0.0;
    for j in 0..n {
        let mut sub = Vec::new();
        for i in 1..n {
            let mut row = Vec::new();
            for k in 0..n {
                if k != j { row.push(m[i][k]); }
            }
            sub.push(row);
        }
        let sign = if j % 2 == 0 { 1.0 } else { -1.0 };
        det += sign * m[0][j] * matrix_determinant(&sub);
    }
    det
}

// FFT
pub fn fft(real: &mut [f64], imag: &mut [f64]) {
    let n = real.len();
    let mut j = 0;
    for i in 1..n - 1 {
        let mut bit = n >> 1;
        while j & bit != 0 {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if i < j {
            real.swap(i, j);
            imag.swap(i, j);
        }
    }

    let mut len = 2;
    while len <= n {
        let angle = -2.0 * std::f64::consts::PI / len as f64;
        let wreal = angle.cos();
        let wimag = angle.sin();
        let mut i = 0;
        while i < n {
            let mut ureal = 1.0;
            let mut uimag = 0.0;
            for k in i..i + len / 2 {
                let l = k + len / 2;
                let treal = ureal * real[l] - uimag * imag[l];
                let timag = ureal * imag[l] + uimag * real[l];
                real[l] = real[k] - treal;
                imag[l] = imag[k] - timag;
                real[k] += treal;
                imag[k] += timag;
                let t = ureal * wreal - uimag * wimag;
                uimag = ureal * wimag + uimag * wreal;
                ureal = t;
            }
            i += len;
        }
        len <<= 1;
    }
}

// Prime sieve
pub fn prime_sieve(limit: usize) -> Vec<usize> {
    let mut is_prime = vec![true; limit + 1];
    is_prime[0] = false;
    is_prime[1] = false;

    for i in 2..=limit {
        if is_prime[i] && i * i <= limit {
            for j in (i * i..=limit).step_by(i) {
                is_prime[j] = false;
            }
        }
    }

    is_prime.iter().enumerate()
        .filter(|(_, &p)| p)
        .map(|(i, _)| i)
        .collect()
}

// GCD and LCM
pub fn gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let t = b;
        b = a % b;
        a = t;
    }
    a
}

pub fn lcm(a: u64, b: u64) -> u64 {
    (a / gcd(a, b)) * b
}

// Fibonacci
pub fn fibonacci(n: u64) -> u64 {
    if n <= 1 { return n; }
    let mut a = 0u64;
    let mut b = 1u64;
    for _ in 2..=n {
        let c = a + b;
        a = b;
        b = c;
    }
    b
}

// Sorting
pub fn quick_sort(arr: &mut [f64]) {
    if arr.len() <= 1 { return; }
    let pivot = arr[arr.len() - 1];
    let mut i = 0;
    for j in 0..arr.len() - 1 {
        if arr[j] <= pivot {
            arr.swap(i, j);
            i += 1;
        }
    }
    arr.swap(i, arr.len() - 1);
    quick_sort(&mut arr[..i]);
    quick_sort(&mut arr[i + 1..]);
}

pub fn merge_sort(arr: &mut [f64]) {
    if arr.len() <= 1 { return; }
    let mid = arr.len() / 2;
    merge_sort(&mut arr[..mid]);
    merge_sort(&mut arr[mid..]);
    let mut merged = Vec::with_capacity(arr.len());
    let mut i = 0;
    let mut j = mid;
    while i < mid && j < arr.len() {
        if arr[i] <= arr[j] {
            merged.push(arr[i]);
            i += 1;
        } else {
            merged.push(arr[j]);
            j += 1;
        }
    }
    merged.extend_from_slice(&arr[i..mid]);
    merged.extend_from_slice(&arr[j..]);
    arr.copy_from_slice(&merged);
}

// Binary search
pub fn binary_search(arr: &[f64], target: f64) -> Option<usize> {
    let mut left = 0;
    let mut right = arr.len();
    while left < right {
        let mid = left + (right - left) / 2;
        if arr[mid] == target {
            return Some(mid);
        } else if arr[mid] < target {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    None
}

// String utilities
pub fn is_palindrome(s: &str) -> bool {
    let chars: Vec<char> = s.chars().collect();
    let len = chars.len();
    for i in 0..len / 2 {
        if chars[i] != chars[len - 1 - i] {
            return false;
        }
    }
    true
}

pub fn reverse_string(s: &str) -> String {
    s.chars().rev().collect()
}

pub fn anagram_check(a: &str, b: &str) -> bool {
    let mut ca: Vec<char> = a.chars().collect();
    let mut cb: Vec<char> = b.chars().collect();
    ca.sort_unstable();
    cb.sort_unstable();
    ca == cb
}

// Statistics
pub fn mean(data: &[f64]) -> f64 {
    data.iter().sum::<f64>() / data.len() as f64
}

pub fn median(data: &[f64]) -> f64 {
    let mut sorted = data.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mid = sorted.len() / 2;
    if sorted.len() % 2 == 0 {
        (sorted[mid - 1] + sorted[mid]) / 2.0
    } else {
        sorted[mid]
    }
}

pub fn variance(data: &[f64]) -> f64 {
    let m = mean(data);
    data.iter().map(|x| (x - m).powi(2)).sum::<f64>() / data.len() as f64
}

pub fn std_dev(data: &[f64]) -> f64 {
    variance(data).sqrt()
}

// Graph algorithms
pub fn dijkstra(graph: &[Vec<(usize, f64)>], start: usize) -> Vec<f64> {
    let n = graph.len();
    let mut dist = vec![f64::INFINITY; n];
    dist[start] = 0.0;
    let mut visited = vec![false; n];
    let mut heap = VecDeque::new();
    heap.push_back((0.0, start));

    while let Some((d, u)) = heap.pop_front() {
        if visited[u] || d > dist[u] { continue; }
        visited[u] = true;
        for &(v, weight) in &graph[u] {
            if dist[u] + weight < dist[v] {
                dist[v] = dist[u] + weight;
                heap.push_back((dist[v], v));
            }
        }
    }
    dist
}

pub fn bfs(graph: &[Vec<usize>], start: usize) -> Vec<usize> {
    let n = graph.len();
    let mut visited = vec![false; n];
    let mut order = Vec::new();
    let mut queue = VecDeque::new();
    queue.push_back(start);
    visited[start] = true;

    while let Some(u) = queue.pop_front() {
        order.push(u);
        for &v in &graph[u] {
            if !visited[v] {
                visited[v] = true;
                queue.push_back(v);
            }
        }
    }
    order
}

// Hash functions
pub fn hash_string(s: &str) -> u64 {
    let mut hash: u64 = 14695981039346656037;
    for byte in s.bytes() {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(1099511628211);
    }
    hash
}

pub fn hash_bytes(data: &[u8]) -> u64 {
    let mut hash: u64 = 14695981039346656037;
    for &byte in data {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(1099511628211);
    }
    hash
}
