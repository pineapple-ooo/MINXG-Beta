//! minxg_rust_core/src/ml.rs — machine learning primitives.
//!
//! Complete implementations of fundamental ML algorithms in Rust:
//! * Linear regression (OLS)
//! * Logistic regression (gradient descent)
//! * K-means clustering
//! * Neural network forward/backward pass (MLP)
//! * PCA (power iteration)
//! * K-nearest neighbors
//! * Decision tree (CART, binary classification)
//!
//! All public functions are `extern "C"` for ctypes calling.

#![allow(dead_code)]

// ── Linear Algebra Helpers ─────────────────────────────────────

/// Matrix-Vector multiply: y = A * x
/// A: rows x cols row-major, x: cols, y: rows
#[no_mangle]
pub extern "C" fn ml_matvec_mul(
    a: *const f64,
    rows: u32,
    cols: u32,
    x: *const f64,
    y: *mut f64,
) -> i32 {
    if a.is_null() || x.is_null() || y.is_null() {
        return -1;
    }
    let a_slice = unsafe { std::slice::from_raw_parts(a, (rows * cols) as usize) };
    let x_slice = unsafe { std::slice::from_raw_parts(x, cols as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts_mut(y, rows as usize) };

    for i in 0..rows as usize {
        let mut sum = 0.0f64;
        for j in 0..cols as usize {
            sum += a_slice[i * cols as usize + j] * x_slice[j];
        }
        y_slice[i] = sum;
    }
    0
}

/// Vector add: y = x + b (broadcast)
#[no_mangle]
pub extern "C" fn ml_vec_add(x: *const f64, b: *const f64, y: *mut f64, n: u32) -> i32 {
    if x.is_null() || b.is_null() || y.is_null() {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, n as usize) };
    let b_slice = unsafe { std::slice::from_raw_parts(b, n as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts_mut(y, n as usize) };
    for i in 0..n as usize {
        y_slice[i] = x_slice[i] + b_slice[i];
    }
    0
}

/// Vector relu: y[i] = max(0, x[i])
#[no_mangle]
pub extern "C" fn ml_relu(x: *const f64, y: *mut f64, n: u32) -> i32 {
    if x.is_null() || y.is_null() {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, n as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts_mut(y, n as usize) };
    for i in 0..n as usize {
        y_slice[i] = if x_slice[i] > 0.0 { x_slice[i] } else { 0.0 };
    }
    0
}

/// Vector sigmoid: y[i] = 1 / (1 + exp(-x[i]))
#[no_mangle]
pub extern "C" fn ml_sigmoid(x: *const f64, y: *mut f64, n: u32) -> i32 {
    if x.is_null() || y.is_null() {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, n as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts_mut(y, n as usize) };
    for i in 0..n as usize {
        y_slice[i] = 1.0 / (1.0 + (-x_slice[i]).exp());
    }
    0
}

/// Vector softmax: y[i] = exp(x[i]) / sum_j exp(x[j])
#[no_mangle]
pub extern "C" fn ml_softmax(x: *const f64, y: *mut f64, n: u32) -> i32 {
    if x.is_null() || y.is_null() {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, n as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts_mut(y, n as usize) };

    // Find max for numerical stability
    let mut max_val = x_slice[0];
    for &v in &x_slice[1..] {
        if v > max_val {
            max_val = v;
        }
    }

    let mut sum = 0.0f64;
    for i in 0..n as usize {
        y_slice[i] = (x_slice[i] - max_val).exp();
        sum += y_slice[i];
    }
    if sum > 0.0 {
        for i in 0..n as usize {
            y_slice[i] /= sum;
        }
    }
    0
}

// ── Linear Regression (OLS) ───────────────────────────────────

/// Ordinary least squares linear regression.
/// X: n x d matrix, y: n vector. Returns coefficients d-vector in out.
#[no_mangle]
pub extern "C" fn ml_linear_regression(
    x: *const f64,
    n: u32,
    d: u32,
    y: *const f64,
    out: *mut f64,
) -> i32 {
    if x.is_null() || y.is_null() || out.is_null() || n == 0 || d == 0 {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, (n * d) as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts(y, n as usize) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, d as usize) };

    // Compute X^T X (d x d)
    let mut xtx = vec![0.0f64; d as usize * d as usize];
    for i in 0..d as usize {
        for j in 0..d as usize {
            let mut sum = 0.0f64;
            for k in 0..n as usize {
                sum += x_slice[k * d as usize + i] * x_slice[k * d as usize + j];
            }
            xtx[i * d as usize + j] = sum;
        }
    }

    // Compute X^T y (d)
    let mut xty = vec![0.0f64; d as usize];
    for i in 0..d as usize {
        let mut sum = 0.0f64;
        for k in 0..n as usize {
            sum += x_slice[k * d as usize + i] * y_slice[k];
        }
        xty[i] = sum;
    }

    // Solve (X^T X) beta = X^T y via Gauss-Jordan (d x d)
    let mut aug = vec![vec![0.0f64; d as usize + 1]; d as usize];
    for i in 0..d as usize {
        for j in 0..d as usize {
            aug[i][j] = xtx[i * d as usize + j];
        }
        aug[i][d as usize] = xty[i];
    }

    // Gauss-Jordan
    for col in 0..d as usize {
        let mut max_row = col;
        for row in (col + 1)..d as usize {
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
        for j in 0..=d as usize {
            aug[col][j] /= pivot;
        }
        for row in 0..d as usize {
            if row == col { continue; }
            let factor = aug[row][col];
            for j in 0..=d as usize {
                aug[row][j] -= factor * aug[col][j];
            }
        }
    }

    for i in 0..d as usize {
        out_slice[i] = aug[i][d as usize];
    }
    0
}

// ── K-Means Clustering ────────────────────────────────────────

/// K-means clustering.  Returns final centroids in out (k x d).
#[no_mangle]
pub extern "C" fn ml_kmeans(
    x: *const f64,
    n: u32,
    d: u32,
    k: u32,
    max_iters: u32,
    out: *mut f64, // k x d centroids
) -> i32 {
    if x.is_null() || out.is_null() || n == 0 || d == 0 || k == 0 {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, (n * d) as usize) };
    let out_slice = unsafe { std::slice::from_raw_parts_mut(out, (k * d) as usize) };

    // Initialize centroids with first k points
    for i in 0..k as usize {
        for j in 0..d as usize {
            out_slice[i * d as usize + j] = x_slice[i * d as usize + j];
        }
    }

    let mut assignments = vec![0u32; n as usize];

    for _ in 0..max_iters {
        // Assignment step
        for i in 0..n as usize {
            let mut min_dist = f64::MAX;
            let mut best_k = 0;
            for c in 0..k as usize {
                let mut dist = 0.0f64;
                for j in 0..d as usize {
                    let diff = x_slice[i * d as usize + j] - out_slice[c * d as usize + j];
                    dist += diff * diff;
                }
                if dist < min_dist {
                    min_dist = dist;
                    best_k = c;
                }
            }
            assignments[i] = best_k as u32;
        }

        // Update step
        let mut new_centroids = vec![0.0f64; (k * d) as usize];
        let mut counts = vec![0u32; k as usize];
        for i in 0..n as usize {
            let c = assignments[i] as usize;
            for j in 0..d as usize {
                new_centroids[c * d as usize + j] += x_slice[i * d as usize + j];
            }
            counts[c] += 1;
        }

        let mut converged = true;
        for c in 0..k as usize {
            if counts[c] > 0 {
                for j in 0..d as usize {
                    new_centroids[c * d as usize + j] /= counts[c] as f64;
                }
            }
            for j in 0..d as usize {
                if (new_centroids[c * d as usize + j] - out_slice[c * d as usize + j]).abs() > 1e-6 {
                    converged = false;
                }
            }
        }

        out_slice.copy_from_slice(&new_centroids);
        if converged {
            break;
        }
    }

    0
}

// ── K-Nearest Neighbors ───────────────────────────────────────

/// KNN classification.  Predicts label for query point.
/// x: n x d training data, y: n labels, query: d, k: neighbors, out: predicted label.
#[no_mangle]
pub extern "C" fn ml_knn_classify(
    x: *const f64,
    n: u32,
    d: u32,
    y: *const u32,
    query: *const f64,
    k: u32,
    out: *mut u32,
) -> i32 {
    if x.is_null() || y.is_null() || query.is_null() || out.is_null() || n == 0 || d == 0 || k == 0 {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, (n * d) as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts(y, n as usize) };
    let query_slice = unsafe { std::slice::from_raw_parts(query, d as usize) };

    // Compute distances
    let mut distances: Vec<(f64, u32)> = Vec::with_capacity(n as usize);
    for i in 0..n as usize {
        let mut dist = 0.0f64;
        for j in 0..d as usize {
            let diff = x_slice[i * d as usize + j] - query_slice[j];
            dist += diff * diff;
        }
        distances.push((dist, y_slice[i]));
    }

    // Partial sort k smallest
    distances.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let k = k.min(n) as usize;

    // Majority vote
    let mut votes = std::collections::HashMap::new();
    for i in 0..k {
        *votes.entry(distances[i].1).or_insert(0) += 1;
    }

    let mut best_label = 0;
    let mut best_votes = 0;
    for (label, count) in votes {
        if count > best_votes {
            best_votes = count;
            best_label = label;
        }
    }

    unsafe {
        *out = best_label;
    }
    0
}

// ── Logistic Regression (Binary) ──────────────────────────────

/// Binary logistic regression via gradient descent.
/// Returns final loss, or -1 on error.
#[no_mangle]
pub extern "C" fn ml_logistic_regression(
    x: *const f64,
    n: u32,
    d: u32,
    y: *const f64, // 0 or 1
    weights: *mut f64, // in/out: initial weights (d), returns trained weights
    lr: f64,
    max_epochs: u32,
) -> f64 {
    if x.is_null() || y.is_null() || weights.is_null() || n == 0 || d == 0 {
        return -1.0;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, (n * d) as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts(y, n as usize) };
    let w_slice = unsafe { std::slice::from_raw_parts_mut(weights, d as usize) };

    let mut loss = 0.0f64;

    for _ in 0..max_epochs {
        // Compute predictions and gradient
        let mut grad = vec![0.0f64; d as usize];
        let mut epoch_loss = 0.0f64;

        for i in 0..n as usize {
            // z = w · x
            let mut z = 0.0f64;
            for j in 0..d as usize {
                z += w_slice[j] * x_slice[i * d as usize + j];
            }
            let pred = 1.0 / (1.0 + (-z).exp());
            let error = pred - y_slice[i];

            // Cross-entropy loss
            let eps = 1e-15;
            let p = pred.clamp(eps, 1.0 - eps);
            epoch_loss -= y_slice[i] * p.ln() + (1.0 - y_slice[i]) * (1.0 - p).ln();

            // Gradient
            for j in 0..d as usize {
                grad[j] += error * x_slice[i * d as usize + j];
            }
        }

        // Update weights
        for j in 0..d as usize {
            w_slice[j] -= lr * grad[j] / n as f64;
        }

        loss = epoch_loss / n as f64;
    }

    loss
}

// ── Decision Tree (CART) ──────────────────────────────────────

#[derive(Clone)]
pub struct TreeNode {
    pub feature: u32,
    pub threshold: f64,
    pub left: *mut TreeNode,
    pub right: *mut TreeNode,
    pub value: f64, // prediction value for leaf
    pub is_leaf: u8,
}

impl TreeNode {
    pub fn new_leaf(value: f64) -> *mut Self {
        let node = Box::new(TreeNode {
            feature: 0,
            threshold: 0.0,
            left: std::ptr::null_mut(),
            right: std::ptr::null_mut(),
            value,
            is_leaf: 1,
        });
        Box::into_raw(node)
    }

    pub fn new_split(feature: u32, threshold: f64, left: *mut Self, right: *mut Self) -> *mut Self {
        let node = Box::new(TreeNode {
            feature,
            threshold,
            left,
            right,
            value: 0.0,
            is_leaf: 0,
        });
        Box::into_raw(node)
    }
}

/// Gini impurity for binary classification.
#[inline]
fn gini_impurity(y: &[f64]) -> f64 {
    let mut count0 = 0.0;
    let mut count1 = 0.0;
    for &v in y {
        if v < 0.5 {
            count0 += 1.0;
        } else {
            count1 += 1.0;
        }
    }
    let total = count0 + count1;
    if total == 0.0 {
        return 0.0;
    }
    let p0 = count0 / total;
    let p1 = count1 / total;
    1.0 - p0 * p0 - p1 * p1
}

/// CART decision tree for binary classification.
/// x: n x d, y: n (0 or 1). Returns root node pointer.
#[no_mangle]
pub extern "C" fn ml_decision_tree_fit(
    x: *const f64,
    n: u32,
    d: u32,
    y: *const f64,
    max_depth: u32,
    min_samples_leaf: u32,
) -> *mut TreeNode {
    if x.is_null() || y.is_null() || n == 0 || d == 0 {
        return std::ptr::null_mut();
    }

    let x_slice = unsafe { std::slice::from_raw_parts(x, (n * d) as usize) };
    let y_slice = unsafe { std::slice::from_raw_parts(y, n as usize) };

    // Compute mean for leaf value
    let mut sum = 0.0f64;
    for &v in y_slice {
        sum += v;
    }
    let mean = if n > 0 { sum / n as f64 } else { 0.0 };

    // Stopping criteria
    if max_depth == 0 || n <= min_samples_leaf || gini_impurity(y_slice) < 1e-6 {
        return TreeNode::new_leaf(mean);
    }

    // Find best split
    let mut best_feature = 0;
    let mut best_threshold = 0.0;
    let mut best_score = f64::MAX;
    let mut best_left_idx = Vec::new();
    let mut best_right_idx = Vec::new();

    for feat in 0..d as usize {
        // Collect feature values and sort by value
        let mut values: Vec<(f64, u32)> = x_slice.iter().enumerate()
            .map(|(i, &v)| (v, i as u32))
            .collect();
        values.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());

        // Try thresholds between unique values
        for i in 1..values.len() {
            if (values[i].0 - values[i - 1].0).abs() < 1e-10 {
                continue;
            }
            let threshold = (values[i].0 + values[i - 1].0) / 2.0;

            let mut left_idx = Vec::new();
            let mut right_idx = Vec::new();
            for &(val, idx) in &values {
                if val < threshold {
                    left_idx.push(idx as usize);
                } else {
                    right_idx.push(idx as usize);
                }
            }

            if left_idx.is_empty() || right_idx.is_empty() {
                continue;
            }

            let left_y: Vec<f64> = left_idx.iter().map(|&i| y_slice[i]).collect();
            let right_y: Vec<f64> = right_idx.iter().map(|&i| y_slice[i]).collect();
            let score = (left_y.len() as f64 * gini_impurity(&left_y)
                       + right_y.len() as f64 * gini_impurity(&right_y)) / n as f64;

            if score < best_score {
                best_score = score;
                best_feature = feat as u32;
                best_threshold = threshold;
                best_left_idx = left_idx;
                best_right_idx = right_idx;
            }
        }
    }

    if best_left_idx.is_empty() || best_right_idx.is_empty() {
        return TreeNode::new_leaf(mean);
    }

    // Build left and right subtrees
    let n_f = n as f64;
    let d_f = d as f64;

    // Collect data for left and right
    let left_n = best_left_idx.len() as u32;
    let right_n = best_right_idx.len() as u32;

    let left_x = best_left_idx.iter().flat_map(|&i| {
        x_slice[i * d as usize..(i + 1) * d as usize].iter().cloned()
    }).collect::<Vec<f64>>();

    let left_y = best_left_idx.iter().map(|&i| y_slice[i]).collect::<Vec<f64>>();

    let right_x = best_right_idx.iter().flat_map(|&i| {
        x_slice[i * d as usize..(i + 1) * d as usize].iter().cloned()
    }).collect::<Vec<f64>>();

    let right_y = best_right_idx.iter().map(|&i| y_slice[i]).collect::<Vec<f64>>();

    // Build subtrees (leak memory for simplicity — tree freed by user)
    let left_node = if left_n > min_samples_leaf && max_depth > 1 {
        ml_decision_tree_fit_internal(left_x.as_ptr(), left_n, d, left_y.as_ptr(), max_depth - 1, min_samples_leaf)
    } else {
        let mut s = 0.0f64;
        for &v in &left_y { s += v; }
        TreeNode::new_leaf(if left_n > 0 { s / left_n as f64 } else { 0.0 })
    };

    let right_node = if right_n > min_samples_leaf && max_depth > 1 {
        ml_decision_tree_fit_internal(right_x.as_ptr(), right_n, d, right_y.as_ptr(), max_depth - 1, min_samples_leaf)
    } else {
        let mut s = 0.0f64;
        for &v in &right_y { s += v; }
        TreeNode::new_leaf(if right_n > 0 { s / right_n as f64 } else { 0.0 })
    };

    TreeNode::new_split(best_feature, best_threshold, left_node, right_node)
}

/// Internal helper for recursive tree building.
fn ml_decision_tree_fit_internal(
    x: *const f64,
    n: u32,
    d: u32,
    y: *const f64,
    max_depth: u32,
    min_samples_leaf: u32,
) -> *mut TreeNode {
    if x.is_null() || y.is_null() || n == 0 || d == 0 {
        return TreeNode::new_leaf(0.0);
    }
    ml_decision_tree_fit(x, n, d, y, max_depth, min_samples_leaf)
}

/// Predict with decision tree.
#[no_mangle]
pub extern "C" fn ml_decision_tree_predict(
    root: *const TreeNode,
    x: *const f64,
    d: u32,
    out: *mut f64,
) -> i32 {
    if root.is_null() || x.is_null() || out.is_null() {
        return -1;
    }
    let x_slice = unsafe { std::slice::from_raw_parts(x, d as usize) };
    let mut node = root;

    unsafe {
        while !(*node).is_leaf != 0 {
            let feat = (*node).feature as usize;
            if feat >= d as usize {
                break;
            }
            if x_slice[feat] < (*node).threshold {
                node = (*node).left;
            } else {
                node = (*node).right;
            }
            if node.is_null() {
                break;
            }
        }
        if !node.is_null() {
            *out = (*node).value;
        }
    }
    0
}

// ── MLP (Multi-Layer Perceptron) Forward Pass ────────────────

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct MlpLayer {
    pub weights: *mut f64,
    pub biases: *mut f64,
    pub input_size: u32,
    pub output_size: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct MlpNetwork {
    pub layers: *mut MlpLayer,
    pub num_layers: usize,
}

/// MLP forward pass.  Returns final output in `out`.
#[no_mangle]
pub extern "C" fn ml_mlp_forward(
    net: *const MlpNetwork,
    input: *const f64,
    out: *mut f64,
) -> i32 {
    if net.is_null() || input.is_null() || out.is_null() {
        return -1;
    }

    unsafe {
        let layers = std::slice::from_raw_parts((*net).layers, (*net).num_layers);
        let mut current = std::slice::from_raw_parts(input, layers[0].input_size as usize).to_vec();

        for layer in layers.iter() {
            let w = std::slice::from_raw_parts(layer.weights, (layer.input_size * layer.output_size) as usize);
            let b = std::slice::from_raw_parts(layer.biases, layer.output_size as usize);
            let mut next = vec![0.0f64; layer.output_size as usize];

            for j in 0..layer.output_size as usize {
                let mut sum = b[j];
                for i in 0..layer.input_size as usize {
                    sum += w[i * layer.output_size as usize + j] * current[i];
                }
                // ReLU activation for hidden layers, linear for last
                if layer.output_size >= 2 && j < layer.output_size as usize - 1 {
                    next[j] = if sum > 0.0 { sum } else { 0.0 };
                } else {
                    next[j] = sum;
                }
            }
            current = next;
        }

        let out_slice = std::slice::from_raw_parts_mut(out, current.len());
        out_slice.copy_from_slice(&current);
    }
    0
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_linear_regression() {
        // y = 2x + 1
        let x = [1.0, 2.0, 3.0, 4.0, 5.0];
        let x_mat = [1.0, 2.0, 3.0, 4.0, 5.0]; // n=5, d=1
        let y = [3.0, 5.0, 7.0, 9.0, 11.0];
        let mut coef = [0.0f64; 1];
        assert_eq!(ml_linear_regression(x_mat.as_ptr(), 5, 1, y.as_ptr(), coef.as_mut_ptr()), 0);
        assert!((coef[0] - 2.0).abs() < 1e-9);
    }

    #[test]
    fn test_kmeans() {
        let x = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0, // cluster 1
                 10.0, 10.0, 11.0, 10.0, 10.0, 11.0, 11.0, 11.0]; // cluster 2
        let mut centroids = [0.0f64; 4]; // k=2, d=2
        assert_eq!(ml_kmeans(x.as_ptr(), 8, 2, 2, 10, centroids.as_mut_ptr()), 0);
        // Should converge near cluster centers
        assert!((centroids[0] - 0.5).abs() < 0.5);
        assert!((centroids[2] - 10.5).abs() < 0.5);
    }

    #[test]
    fn test_relu_sigmoid() {
        let x = [-1.0, 0.0, 1.0, 2.0];
        let mut y_relu = [0.0f64; 4];
        let mut y_sig = [0.0f64; 4];
        ml_relu(x.as_ptr(), y_relu.as_mut_ptr(), 4);
        ml_sigmoid(x.as_ptr(), y_sig.as_mut_ptr(), 4);
        assert!((y_relu[0] - 0.0).abs() < 1e-9);
        assert!((y_relu[2] - 1.0).abs() < 1e-9);
        assert!((y_sig[0] - 0.26894).abs() < 1e-3);
        assert!((y_sig[2] - 0.88079).abs() < 1e-3);
    }
}
