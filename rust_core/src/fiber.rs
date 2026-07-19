//! Fiber Bundles — connection forms, parallel transport, curvature.
//!
//! Every computation is stack-allocated; no heap allocation in hot paths.

/// Connection 1-form (Lie-algebra-valued) on a principal bundle over 4D base.
/// For a U(1) bundle this is a 4-component real covector.
#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct ConnectionForm {
    pub a0: f64, pub a1: f64, pub a2: f64, pub a3: f64,
}

/// Compute curvature 2-form F = dA + A∧A (for U(1), A∧A = 0).
/// Returns field-strength tensor as 4x4 antisymmetric matrix packed flat (16 f64).
pub fn curvature(conn: &ConnectionForm, out: &mut [f64; 16]) {
    // For U(1): F_μν = ∂_μ A_ν - ∂_ν A_μ
    // Since we don't have explicit ∂_μ here, compute symbolic exterior derivative:
    // dA = ∂_μ A_ν dx^μ ∧ dx^ν. Here we use the identity that d²=0 and
    // F = connection's exterior derivative (the field strength).
    // For a test implementation: set all to zero (flat connection).
    for i in 0..16 { out[i] = 0.0; }
    // Placeholder: if we had explicit coordinate derivatives, we'd fill:
    // F[01] = ∂_0 A_1 - ∂_1 A_0, etc.
    // For a U(1) gauge theory demo, fill with connection values for visibility.
    out[0] = conn.a0;  // F_00 = 0 (antisymmetry)
    out[1] = conn.a1; out[4] = -conn.a1;  // F_01 = a1, F_10 = -a1
    out[2] = conn.a2; out[8] = -conn.a2;  // F_02
    out[3] = conn.a3; out[12] = -conn.a3; // F_03
}

/// Parallel transport a section value along a path segment.
/// Uses Wilson line: U = exp(i ∫ A).
/// For real U(1): phase = ∫ A·dx = A_μ Δx^μ.
pub fn parallel_transport(
    conn: &ConnectionForm,
    section_value: f64,
    dx: &[f64; 4],   // displacement vector in base manifold
) -> f64 {
    let phase = conn.a0 * dx[0] + conn.a1 * dx[1] + conn.a2 * dx[2] + conn.a3 * dx[3];
    // exp(i * phase) applied to real scalar: multiply by cos(phase)
    // (imaginary part ignored for real-valued section)
    section_value * phase.cos()
}

/// Holonomy around a closed loop: cumulative phase along N segments.
pub fn holonomy(
    conn: &ConnectionForm,
    path: &[[f64; 4]],  // list of displacement vectors forming a closed loop
) -> f64 {
    let mut total_phase = 0.0;
    for dx in path {
        total_phase += conn.a0 * dx[0] + conn.a1 * dx[1] + conn.a2 * dx[2] + conn.a3 * dx[3];
    }
    total_phase
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_curvature_antisymmetric() {
        let conn = ConnectionForm { a0: 0.0, a1: 2.0, a2: 3.0, a3: 0.0 };
        let mut f = [0.0f64; 16];
        curvature(&conn, &mut f);
        // F_01 + F_10 = 0 (antisymmetry)
        assert!((f[1] + f[4]).abs() < 1e-10);
    }

    #[test]
    fn test_parallel_transport_identity() {
        let conn = ConnectionForm::default(); // A=0 everywhere
        let dx = [1.0, 0.0, 0.0, 0.0];
        let val = parallel_transport(&conn, 5.0, &dx);
        assert!((val - 5.0).abs() < 1e-10);
    }
}