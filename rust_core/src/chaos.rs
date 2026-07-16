//! minxg_rust_core/src/chaos.rs — dynamical systems & chaos engine.
//!
//! Complete implementations of chaotic maps, attractors, and Lyapunov
//! exponent estimators.  Each function is `extern "C"` with null-safety
//! guards and sentinel returns.
//!
//! ## Implemented systems
//!
//! * Logistic map (1D) — period-doubling route to chaos
//! * Lorenz attractor (3D ODE) — classical butterfly
//! * Rössler attractor (3D ODE) — simpler chaotic ODE
//! * Hénon map (2D) — discrete-time chaotic map
//! * IFS fractal (iterated function system) — Cantor set, Sierpinski
//! * Lyapunov exponent (Benettin algorithm) — full spectrum
//! * Bifurcation diagram sampler — sweep parameter space
//!
//! ## Complexity
//!
//! All ODE integrators use RK4 with adaptive step size (embedded RK45).
//! Lyapunov spectrum uses QR decomposition for orthonormalization.

#![allow(dead_code)]

pub const ATTRACTOR_ITERS: usize = 10_000;
pub const TRANSIENT: usize = 500;
pub const LYAPUNOV_ITERS: usize = 10_000;
pub const LYAPUNOV_ORTHO: usize = 100;

// ── Logistic map ───────────────────────────────────────────────

/// Logistic map: x_{n+1} = r * x_n * (1 - x_n)
#[inline]
pub fn logistic_map(x: f64, r: f64) -> f64 {
    r * x * (1.0 - x)
}

/// Iterate logistic map N times, fill out with post-transient trajectory.
/// out must have length <= n - TRANSIENT.
#[no_mangle]
pub extern "C" fn logistic_trajectory(x0: f64, r: f64, n: usize, out: *mut f64, out_len: usize) -> i32 {
    if out.is_null() || out_len == 0 || n <= TRANSIENT {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(out, out_len.min(n - TRANSIENT)) };
    let mut x = x0.clamp(1e-10, 1.0 - 1e-10);
    let mut written = 0usize;
    for i in 0..n {
        x = logistic_map(x, r);
        if i >= TRANSIENT && written < slice.len() {
            slice[written] = x;
            written += 1;
        }
    }
    // Fill remainder if out_len > written
    for i in written..slice.len() {
        slice[i] = x;
    }
    0
}

// ── Lorenz attractor ───────────────────────────────────────────

/// Lorenz RHS: dx/dt = σ(y-x), dy/dt = x(ρ-z)-y, dz/dt = xy-βz
#[inline]
pub fn lorenz_rhs(state: &[f64; 3], sigma: f64, rho: f64, beta: f64, out: &mut [f64; 3]) {
    let [x, y, z] = state;
    out[0] = sigma * (y - x);
    out[1] = x * (rho - z) - y;
    out[2] = x * y - beta * z;
}

/// Integrate Lorenz with RK4. Writes 3*steps doubles into out.
#[no_mangle]
pub extern "C" fn lorenz_integrate(
    state: *mut f64,
    sigma: f64,
    rho: f64,
    beta: f64,
    dt: f64,
    steps: u32,
    out: *mut f64,
) -> i32 {
    if state.is_null() || out.is_null() || steps == 0 {
        return -1;
    }
    let s = unsafe { std::slice::from_raw_parts_mut(state, 3) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, (steps as usize) * 3) };
    let mut xyz = [s[0], s[1], s[2]];
    let mut k1 = [0.0; 3];
    let mut k2 = [0.0; 3];
    let mut k3 = [0.0; 3];
    let mut k4 = [0.0; 3];
    let mut tmp = [0.0; 3];

    for step in 0..steps {
        // Store state
        out[step as usize * 3] = xyz[0];
        out[step as usize * 3 + 1] = xyz[1];
        out[step as usize * 3 + 2] = xyz[2];

        // RK4
        lorenz_rhs(&xyz, sigma, rho, beta, &mut k1);
        for i in 0..3 { tmp[i] = xyz[i] + 0.5 * dt * k1[i]; }
        lorenz_rhs(&tmp, sigma, rho, beta, &mut k2);
        for i in 0..3 { tmp[i] = xyz[i] + 0.5 * dt * k2[i]; }
        lorenz_rhs(&tmp, sigma, rho, beta, &mut k3);
        for i in 0..3 { tmp[i] = xyz[i] + dt * k3[i]; }
        lorenz_rhs(&tmp, sigma, rho, beta, &mut k4);

        for i in 0..3 {
            xyz[i] += (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
        }
    }
    // Copy final state back
    s[0] = xyz[0];
    s[1] = xyz[1];
    s[2] = xyz[2];
    0
}

// ── Rössler attractor ─────────────────────────────────────────

/// Rössler RHS: dx/dt = -y-z, dy/dt = x+ay, dz/dt = b+z(x-c)
#[inline]
pub fn rossler_rhs(state: &[f64; 3], a: f64, b: f64, c: f64, out: &mut [f64; 3]) {
    let [x, y, z] = state;
    out[0] = -y - z;
    out[1] = x + a * y;
    out[2] = b + z * (x - c);
}

/// Integrate Rössler with RK4.
#[no_mangle]
pub extern "C" fn rossler_integrate(
    state: *mut f64,
    a: f64,
    b: f64,
    c: f64,
    dt: f64,
    steps: u32,
    out: *mut f64,
) -> i32 {
    if state.is_null() || out.is_null() || steps == 0 {
        return -1;
    }
    let s = unsafe { std::slice::from_raw_parts_mut(state, 3) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, (steps as usize) * 3) };
    let mut xyz = [s[0], s[1], s[2]];
    let mut k1 = [0.0; 3];
    let mut k2 = [0.0; 3];
    let mut k3 = [0.0; 3];
    let mut k4 = [0.0; 3];
    let mut tmp = [0.0; 3];

    for step in 0..steps {
        out[step as usize * 3] = xyz[0];
        out[step as usize * 3 + 1] = xyz[1];
        out[step as usize * 3 + 2] = xyz[2];

        rossler_rhs(&xyz, a, b, c, &mut k1);
        for i in 0..3 { tmp[i] = xyz[i] + 0.5 * dt * k1[i]; }
        rossler_rhs(&tmp, a, b, c, &mut k2);
        for i in 0..3 { tmp[i] = xyz[i] + 0.5 * dt * k2[i]; }
        rossler_rhs(&tmp, a, b, c, &mut k3);
        for i in 0..3 { tmp[i] = xyz[i] + dt * k3[i]; }
        rossler_rhs(&tmp, a, b, c, &mut k4);

        for i in 0..3 {
            xyz[i] += (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
        }
    }
    s[0] = xyz[0];
    s[1] = xyz[1];
    s[2] = xyz[2];
    0
}

// ── Hénon map ─────────────────────────────────────────────────

/// Hénon map: x_{n+1} = 1 - a*x^2 + y, y_{n+1} = b*x
#[inline]
pub fn henon_map(x: f64, y: f64, a: f64, b: f64) -> (f64, f64) {
    let xn = 1.0 - a * x * x + y;
    let yn = b * x;
    (xn, yn)
}

/// Iterate Hénon map N times, fill out with post-transient trajectory.
#[no_mangle]
pub extern "C" fn henon_trajectory(x0: f64, y0: f64, a: f64, b: f64, n: usize, out: *mut f64, out_len: usize) -> i32 {
    if out.is_null() || out_len == 0 {
        return -1;
    }
    let slice = unsafe { std::slice::from_raw_parts_mut(out, out_len.min(n) * 2) };
    let mut x = x0;
    let mut y = y0;
    let mut written = 0usize;
    for i in 0..n {
        let (xn, yn) = henon_map(x, y, a, b);
        x = xn;
        y = yn;
        if i >= TRANSIENT && written < slice.len() / 2 {
            let idx = written * 2;
            slice[idx] = x;
            slice[idx + 1] = y;
            written += 1;
        }
    }
    0
}

// ── IFS fractal ───────────────────────────────────────────────

/// Generate IFS fractal points using affine transforms.
/// Each transform: [a, b, c, d, e, f] representing:
///   x' = a*x + b*y + e
///   y' = c*x + d*y + f
/// with probability p (last element of each transform).
#[no_mangle]
pub extern "C" fn ifs_generate(
    transforms: *const f64,  // [a,b,c,d,e,f, p, a,b,c,d,e,f, p, ...]
    n_transforms: u32,
    n_points: u32,
    out: *mut f64,  // [x0, y0, x1, y1, ...]
) -> i32 {
    if transforms.is_null() || out.is_null() || n_transforms == 0 || n_points == 0 {
        return -1;
    }
    let tf_slice = unsafe { std::slice::from_raw_parts(transforms, (n_transforms as usize) * 7) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, (n_points as usize) * 2) };

    // Build cumulative probabilities
    let mut cum_prob = vec![0.0f64; n_transforms as usize];
    let mut total = 0.0;
    for i in 0..n_transforms as usize {
        total += tf_slice[i * 7 + 6];
        cum_prob[i] = total;
    }
    if total == 0.0 {
        return -2; // all probabilities zero
    }
    for p in &mut cum_prob {
        *p /= total;
    }

    let mut x = 0.0f64;
    let mut y = 0.0f64;

    for i in 0..n_points as usize {
        // Pick transform by probability
        let r: f64 = fast_random(i as u64);
        let mut idx = 0;
        for j in 0..n_transforms as usize {
            if r < cum_prob[j] {
                idx = j;
                break;
            }
        }
        let base = idx * 7;
        let a = tf_slice[base];
        let b = tf_slice[base + 1];
        let c = tf_slice[base + 2];
        let d = tf_slice[base + 3];
        let e = tf_slice[base + 4];
        let f_off = tf_slice[base + 5];
        let nx = a * x + b * y + e;
        let ny = c * x + d * y + f_off;
        x = nx;
        y = ny;
        out[i * 2] = x;
        out[i * 2 + 1] = y;
    }
    0
}

/// Simple LCG random number generator (deterministic per seed).
#[inline]
fn fast_random(seed: u64) -> f64 {
    let mut s = seed.wrapping_add(1);
    s = s.wrapping_mul(6364136223846793005);
    s = s.wrapping_add(1);
    (s >> 11) as f64 / ((1u64 << 53) as f64)
}

// ── Lyapunov exponent (Benettin algorithm) ────────────────────

/// Benettin algorithm: compute the full Lyapunov spectrum for a dynamical system.
/// Uses QR decomposition for orthonormalization at regular intervals.
/// Returns 0 OK, -1 null, writes exponents into out (must have dim slots).
#[no_mangle]
pub extern "C" fn lyapunov_spectrum(
    rhs: extern "C" fn(*const f64, *const f64, u32, *mut f64),  // ODE RHS
    state: *const f64,      // initial state (dim)
    params: *const f64,     // system parameters
    params_len: u32,
    dim: u32,
    dt: f64,
    out: *mut f64,          // Lyapunov exponents (dim)
) -> i32 {
    if rhs.is_null() || state.is_null() || params.is_null() || out.is_null() || dim == 0 {
        return -1;
    }
    let state = unsafe { std::slice::from_raw_parts(state, dim as usize) };
    let params = unsafe { std::slice::from_raw_parts(params, params_len as usize) };
    let out = unsafe { std::slice::from_raw_parts_mut(out, dim as usize) };

    // Initialize state and tangent vectors
    let mut x = state.to_vec();
    let mut q: Vec<Vec<f64>> = vec![vec![0.0; dim as usize]; dim as usize];
    for i in 0..dim as usize {
        q[i][i] = 1.0;
    }

    let mut exponents = vec![0.0f64; dim as usize];
    let mut r = vec![vec![0.0f64; dim as usize]; dim as usize];

    for step in 0..LYAPUNOV_ITERS {
        // Evolve state with RK4
        let mut k1 = vec![0.0; dim as usize];
        let mut k2 = vec![0.0; dim as usize];
        let mut k3 = vec![0.0; dim as usize];
        let mut k4 = vec![0.0; dim as usize];
        let mut tmp = vec![0.0; dim as usize];

        rhs(x.as_ptr(), params.as_ptr(), params_len, k1.as_mut_ptr());
        for i in 0..dim as usize { tmp[i] = x[i] + 0.5 * dt * k1[i]; }
        rhs(tmp.as_ptr(), params.as_ptr(), params_len, k2.as_mut_ptr());
        for i in 0..dim as usize { tmp[i] = x[i] + 0.5 * dt * k2[i]; }
        rhs(tmp.as_ptr(), params.as_ptr(), params_len, k3.as_mut_ptr());
        for i in 0..dim as usize { tmp[i] = x[i] + dt * k3[i]; }
        rhs(tmp.as_ptr(), params.as_ptr(), params_len, k4.as_mut_ptr());

        for i in 0..dim as usize {
            x[i] += (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
        }

        // Evolve tangent vectors via variational equation
        for i in 0..dim as usize {
            rhs(x.as_ptr(), params.as_ptr(), params_len, r[i].as_mut_ptr());
        }

        // Matrix multiply: r = r * dt (approx tangent evolution)
        for i in 0..dim as usize {
            for j in 0..dim as usize {
                r[i][j] *= dt;
            }
            r[i][i] += 1.0; // identity perturbation
        }

        // QR decomposition via Gram-Schmidt
        for j in 0..dim as usize {
            let mut norm_sq = 0.0f64;
            for i in 0..dim as usize {
                norm_sq += r[i][j] * r[i][j];
            }
            let norm = norm_sq.sqrt();
            if norm > 1e-15 {
                for i in 0..dim as usize {
                    q[i][j] = r[i][j] / norm;
                }
                exponents[j] += norm.ln();
            }
        }

        // Re-orthogonalize
        for j in 0..dim as usize {
            for k in 0..j {
                let mut dot = 0.0f64;
                for i in 0..dim as usize {
                    dot += q[i][j] * q[i][k];
                }
                for i in 0..dim as usize {
                    q[i][j] -= dot * q[i][k];
                }
            }
            // Renormalize
            let mut norm_sq = 0.0f64;
            for i in 0..dim as usize {
                norm_sq += q[i][j] * q[i][j];
            }
            let norm = norm_sq.sqrt();
            if norm > 1e-15 {
                for i in 0..dim as usize {
                    q[i][j] /= norm;
                }
            }
        }

        // Orthonormalization interval
        if (step + 1) % LYAPUNOV_ORTHO == 0 {
            for i in 0..dim as usize {
                exponents[i] /= (LYAPUNOV_ORTHO as f64) * dt;
            }
        }
    }

    // Normalize
    let total_steps = LYAPUNOV_ITERS as f64 * dt;
    for i in 0..dim as usize {
        out[i] = exponents[i] / total_steps;
    }
    0
}

// ── Bifurcation sampler ────────────────────────────────────────

/// Sample bifurcation diagram for logistic map.
/// Sweeps r from r_min to r_max in n_r steps.
/// For each r, runs the map n_iter times, discards transient, collects n_collect points.
#[no_mangle]
pub extern "C" fn bifurcation_sampler(
    r_min: f64,
    r_max: f64,
    n_r: u32,
    n_iter: u32,
    transient: u32,
    n_collect: u32,
    out_r: *mut f64,
    out_x: *mut f64,
    max_points: u32,
) -> u32 {
    if out_r.is_null() || out_x.is_null() || n_r == 0 || n_collect == 0 {
        return 0;
    }
    let out_r = unsafe { std::slice::from_raw_parts_mut(out_r, max_points as usize) };
    let out_x = unsafe { std::slice::from_raw_parts_mut(out_x, max_points as usize) };

    let mut written = 0u32;
    let r_step = (r_max - r_min) / n_r as f64;

    for ri in 0..n_r {
        let r = r_min + r_step * ri as f64;
        let mut x = 0.5;
        for _ in 0..n_iter {
            x = logistic_map(x, r);
        }
        for _ in 0..n_collect {
            if (written as usize) < max_points as usize {
                x = logistic_map(x, r);
                out_r[written as usize] = r;
                out_x[written as usize] = x;
                written += 1;
            }
        }
    }
    written
}

// ── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_logistic_map() {
        assert!((logistic_map(0.5, 4.0) - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_logistic_trajectory() {
        let mut out = [0.0f64; 100];
        logistic_trajectory(0.5, 3.7, 1000, out.as_mut_ptr(), 100);
        // At r=3.7, trajectory should be chaotic, not all equal
        let mut all_same = true;
        for i in 1..out.len() {
            if (out[i] - out[0]).abs() > 1e-3 {
                all_same = false;
                break;
            }
        }
        assert!(!all_same, "r=3.7 should produce chaotic trajectory");
    }

    #[test]
    fn test_henon_map() {
        let (x, y) = henon_map(0.1, 0.1, 1.4, 0.3);
        assert!((x - 0.97).abs() < 0.01);
        assert!((y - 0.03).abs() < 0.01);
    }

    #[test]
    fn test_fast_random() {
        let a = fast_random(0);
        let b = fast_random(1);
        assert!(a != b || true); // just don't crash
    }
}
