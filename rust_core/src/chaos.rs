//! Dynamical systems & chaos — Logistic map, Lorenz attractor, IFS fractal.

/// Number of iterations for attractor sampling
pub const ATTRACTOR_ITERS: usize = 10_000;
pub const TRANSIENT: usize = 500;

/// Logistic map: x_{n+1} = r * x_n * (1 - x_n)
pub fn logistic_map(x: f64, r: f64) -> f64 {
    r * x * (1.0 - x)
}

/// Iterate the logistic map N times, return trajectory (pre-allocated slice).
pub fn logistic_trajectory(x0: f64, r: f64, n: usize, out: &mut [f64]) {
    let mut x = x0;
    for i in 0..n {
        x = logistic_map(x, r);
        if i >= TRANSIENT && i - TRANSIENT < out.len() {
            out[i - TRANSIENT] = x;
        }
    }
    for i in (n - TRANSIENT).min(out.len())..out.len() {
        out[i] = x; // fill remainder with last value
    }
}

/// Lorenz system: dx/dt = σ(y-x), dy/dt = x(ρ-z)-y, dz/dt = xy-βz
pub fn lorenz_rhs(state: &[f64; 3], sigma: f64, rho: f64, beta: f64, out: &mut [f64; 3]) {
    out[0] = sigma * (state[1] - state[0]);
    out[1] = state[0] * (rho - state[2]) - state[1];
    out[2] = state[0] * state[1] - beta * state[2];
}

/// Integrate Lorenz with fixed-step Euler (RK4 overkill for simple clients).
/// `state` is mutable in/out; `steps` iterations with `dt`.
pub fn lorenz_integrate(state: &mut [f64; 3], sigma: f64, rho: f64, beta: f64, dt: f64, steps: u32) {
    for _ in 0..steps {
        let mut k = [0.0; 3];
        lorenz_rhs(state, sigma, rho, beta, &mut k);
        state[0] += dt * k[0];
        state[1] += dt * k[1];
        state[2] += dt * k[2];
    }
}

/// IFS (Iterated Function System) — Barnsley fern or Sierpinski.
/// `transforms` is Nx6: [a,b,c,d,e,f, prob] packed flat.
/// `n_transforms`: number of transforms.
/// `points`: pre-allocated (iterations × 2) buffer, filled with (x,y).
pub fn ifs_generate(
    transforms: &[f64], n_transforms: usize,
    seed_x: f64, seed_y: f64,
    iterations: usize,
    points: &mut [f64],
) {
    let mut x = seed_x;
    let mut y = seed_y;
    for i in 0..iterations {
        // Pick transform by cumulative probability
        let r: f64 = fast_rand(); // deterministic-ish placeholder
        let mut cum = 0.0;
        let mut chosen = 0usize;
        for t in 0..n_transforms {
            let base = t * 7;
            cum += transforms[base + 6];
            if r <= cum { chosen = t; break; }
        }
        let base = chosen * 7;
        let (a, b, c, d, e, f) = (
            transforms[base], transforms[base+1], transforms[base+2],
            transforms[base+3], transforms[base+4], transforms[base+5],
        );
        let nx = a * x + b * y + e;
        let ny = c * x + d * y + f;
        x = nx;
        y = ny;
        if i >= 20 {  // skip initial transient
            let idx = (i - 20) * 2;
            if idx + 1 < points.len() {
                points[idx] = x;
                points[idx + 1] = y;
            }
        }
    }
}

/// Simple pseudo-random on [0,1) (for IFS selection; no crypto quality needed).
fn fast_rand() -> f64 {
    // LCG: not cryptographic, but deterministic for reproducibility.
    static mut SEED: u64 = 123456789;
    unsafe {
        SEED = SEED.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        (SEED >> 33) as f64 / (1u64 << 31) as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_logistic_fixed_point_r_2() {
        // r=2, x eventually → 0.5
        let mut x = logistic_map(0.2, 2.0);
        for _ in 0..100 { x = logistic_map(x, 2.0); }
        assert!((x - 0.5).abs() < 1e-6);
    }

    #[test]
    fn test_lorenz_integrate_smoke() {
        let mut state = [1.0, 0.0, 0.0];
        lorenz_integrate(&mut state, 10.0, 28.0, 8.0/3.0, 0.001, 100);
        // state should have moved (not NaN)
        assert!(state[0].is_finite());
        assert!(state[1].is_finite());
    }
}