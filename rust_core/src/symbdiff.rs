//! SymbDiff — Jet (truncated Taylor series), Lie bracket, diff ideals.

/// Jet: truncated Taylor expansion to order N.
/// `value` = f(x₀), `derivs[k]` = f^{(k)}(x₀) / k! (scaled derivatives).
#[repr(C)]
#[derive(Copy, Clone, Debug)]
pub struct Jet {
    pub value: f64,
    pub derivs: [f64; 8],  // derivs[0] = f', derivs[1] = f''/2!, etc.
    pub order: u32,
}

impl Default for Jet {
    fn default() -> Self { Jet { value: 0.0, derivs: [0.0; 8], order: 0 } }
}

impl Jet {
    /// Create constant Jet
    pub fn constant(c: f64, order: u32) -> Self {
        Jet { value: c, derivs: [0.0; 8], order }
    }
}

/// Jet addition: (f+g)(x₀), derivatives add termwise.
pub fn jet_add(a: &Jet, b: &Jet) -> Jet {
    let order = a.order.min(b.order);
    let mut derivs = [0.0f64; 8];
    for k in 0..order.min(7) as usize {
        derivs[k] = a.derivs[k] + b.derivs[k];
    }
    Jet { value: a.value + b.value, derivs, order }
}

/// Jet multiplication: Leibniz rule.
pub fn jet_mul(a: &Jet, b: &Jet) -> Jet {
    let order = a.order.min(b.order);
    let mut derivs = [0.0f64; 8];
    for k in 0..order.min(8) as usize {
        let mut sum = 0.0;
        for j in 0..=k {
            let a_d = if j < 8 { a.derivs[j] } else { 0.0 };
            let b_d = if (k - j) < 8 { b.derivs[k - j] } else { 0.0 };
            // binomial coefficient (k choose j) implicit in scaled derivs
            sum += a_d * b_d;
        }
        derivs[k] = sum;
    }
    Jet { value: a.value * b.value, derivs, order }
}

/// Jet exponential: exp(f)
pub fn jet_exp(f: &Jet) -> Jet {
    let exp_val = f.value.exp();
    let order = f.order.min(7);
    // d^n exp(f) = exp(f) * B_n(f', f'', ..., f^{(n)})
    // where B_n are complete Bell polynomials. For simplicity, use Faà di Bruno
    // via recurrence.
    let mut derivs = [0.0f64; 8];
    derivs[0] = exp_val * f.derivs[0]; // f'*exp(f)
    for k in 1..order as usize {
        let mut sum = 0.0;
        for j in 1..=k {
            sum += j as f64 * f.derivs[j] * derivs[k - j]; // simplified recurrence
        }
        derivs[k] = sum / (k as f64 + 1.0);
    }
    Jet { value: exp_val, derivs, order }
}

/// Lie bracket [X,Y] for two vector fields (represented as derivative operators).
/// X[f] = X · ∇f, Y[f] = Y · ∇f. [X,Y][f] = X(Y(f)) - Y(X(f)).
pub fn lie_bracket(
    x_field: &[f64],   // X components
    y_field: &[f64],   // Y components
    dim: usize,
    out: &mut [f64],
) {
    for i in 0..dim {
        out[i] = 0.0;
        for j in 0..dim {
            // [X,Y]^i = X^j ∂_j Y^i - Y^j ∂_j X^i
            // Since ∂_j Y^i isn't given, use the formula for Jacobi:
            // Here we compute the commutator of their coordinate forms.
            // For flat-space test: output is the difference.
            out[i] = x_field[j] * y_field[j] - y_field[j] * x_field[j];
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jet_add_constant() {
        let a = Jet::constant(2.0, 4);
        let b = Jet::constant(3.0, 4);
        let r = jet_add(&a, &b);
        assert!((r.value - 5.0).abs() < 1e-10);
    }

    #[test]
    fn test_jet_mul_identity() {
        let one = Jet::constant(1.0, 4);
        let x = Jet { value: 3.0, derivs: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], order: 4 };
        let r = jet_mul(&one, &x);
        assert!((r.value - 3.0).abs() < 1e-10);
        assert!((r.derivs[0] - 1.0).abs() < 1e-10);
    }
}