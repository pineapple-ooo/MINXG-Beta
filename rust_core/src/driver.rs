//! Driver engine — RK4 / RK45 ODE integrators with Lagrangian and chaos.

/// State vector for the driver engine.
#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct StateVector {
    pub data: [f64; 8],
    pub len: u32,
}

/// Integration step report
#[repr(C)]
#[derive(Copy, Clone, Debug, Default)]
pub struct StepReport {
    pub energy_delta: f64,
    pub lyapunov_estimate: f64,
    pub is_chaotic: u8,
    pub singularity_detected: u8,
    pub steps_taken: u32,
    pub dt_used: f64,
}

/// FFI-safe ODE RHS: dy/dt = f(y, t).
/// Uses raw pointers so it is ctype-friendly (cffi, ctypes, jni).
pub type OdeRHS = extern "C" fn(
    state: *const f64,
    t: f64,
    params: *const f64,
    params_len: u32,
    out: *mut f64,
    n: u32,
);

/// 4th-order Runge-Kutta single step (fixed dt).
///
/// `rhs` is an `extern "C"` function with signature `OdeRHS`.
/// `state.data[i]` for `i >= state.len` is irrelevant (ignored).
pub fn rk4_step(
    rhs: OdeRHS,
    state: &mut StateVector,
    params: &[f64],
    dt: f64,
    t: f64,
) {
    let n = state.len as usize;
    let y_ptr = state.data.as_ptr();
    let p_ptr = params.as_ptr();
    let p_len = params.len() as u32;

    // k1
    let mut k1 = [0.0f64; 8];
    unsafe {
        rhs(y_ptr, t, p_ptr, p_len, k1.as_mut_ptr(), n as u32);
    }

    // k2
    let mut y2 = [0.0f64; 8];
    for i in 0..n {
        y2[i] = state.data[i] + 0.5 * dt * k1[i];
    }
    let mut k2 = [0.0f64; 8];
    unsafe {
        rhs(y2.as_ptr(), t + 0.5 * dt, p_ptr, p_len, k2.as_mut_ptr(), n as u32);
    }

    // k3
    let mut y3 = [0.0f64; 8];
    for i in 0..n {
        y3[i] = state.data[i] + 0.5 * dt * k2[i];
    }
    let mut k3 = [0.0f64; 8];
    unsafe {
        rhs(y3.as_ptr(), t + 0.5 * dt, p_ptr, p_len, k3.as_mut_ptr(), n as u32);
    }

    // k4
    let mut y4 = [0.0f64; 8];
    for i in 0..n {
        y4[i] = state.data[i] + dt * k3[i];
    }
    let mut k4 = [0.0f64; 8];
    unsafe {
        rhs(y4.as_ptr(), t + dt, p_ptr, p_len, k4.as_mut_ptr(), n as u32);
    }

    // Combine — write into state AFTER k4 borrow ends.
    let mut updates = [0.0f64; 8];
    for i in 0..n {
        updates[i] = state.data[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
    }
    for i in 0..n {
        state.data[i] = updates[i];
    }
}

/// RK45 (Fehlberg 4(5)) adaptive step.
/// Returns the recommended next dt (clamped to `[dt_min, dt_max]`).
pub fn rk45_step(
    rhs: OdeRHS,
    state: &mut StateVector,
    params: &[f64],
    t: f64,
    dt: f64,
    rtol: f64,
    atol: f64,
    dt_min: f64,
    dt_max: f64,
) -> f64 {
    let n = state.len as usize;
    let y_ptr = state.data.as_ptr();
    let p_ptr = params.as_ptr();
    let p_len = params.len() as u32;

    // Butcher tableau for RK45
    let mut k1 = [0.0f64; 8];
    unsafe {
        rhs(y_ptr, t, p_ptr, p_len, k1.as_mut_ptr(), n as u32);
    }

    // k2: y + dt*(1/4)*k1
    let mut tmp = [0.0f64; 8];
    for i in 0..n {
        tmp[i] = state.data[i] + dt * 0.25 * k1[i];
    }
    let mut k2 = [0.0f64; 8];
    unsafe {
        rhs(tmp.as_ptr(), t + dt * 0.25, p_ptr, p_len, k2.as_mut_ptr(), n as u32);
    }

    // k3: y + dt*(3/32 k1 + 9/32 k2)
    for i in 0..n {
        tmp[i] = state.data[i] + dt * (3.0 / 32.0 * k1[i] + 9.0 / 32.0 * k2[i]);
    }
    let mut k3 = [0.0f64; 8];
    unsafe {
        rhs(
            tmp.as_ptr(),
            t + dt * 3.0 / 8.0,
            p_ptr,
            p_len,
            k3.as_mut_ptr(),
            n as u32,
        );
    }

    // k4: 1932/2197 k1 - 7200/2197 k2 + 7296/2197 k3
    for i in 0..n {
        tmp[i] = state.data[i]
            + dt * (1932.0 / 2197.0 * k1[i] - 7200.0 / 2197.0 * k2[i] + 7296.0 / 2197.0 * k3[i]);
    }
    let mut k4 = [0.0f64; 8];
    unsafe {
        rhs(
            tmp.as_ptr(),
            t + dt * 12.0 / 13.0,
            p_ptr,
            p_len,
            k4.as_mut_ptr(),
            n as u32,
        );
    }

    // k5: 439/216 k1 - 8 k2 + 3680/513 k3 - 845/4104 k4
    for i in 0..n {
        tmp[i] = state.data[i]
            + dt * (439.0 / 216.0 * k1[i] - 8.0 * k2[i] + 3680.0 / 513.0 * k3[i]
                - 845.0 / 4104.0 * k4[i]);
    }
    let mut k5 = [0.0f64; 8];
    unsafe {
        rhs(tmp.as_ptr(), t + dt, p_ptr, p_len, k5.as_mut_ptr(), n as u32);
    }

    // k6: -8/27 k1 + 2 k2 - 3544/2565 k3 + 1859/4104 k4 - 11/40 k5
    for i in 0..n {
        tmp[i] = state.data[i]
            + dt * (-8.0 / 27.0 * k1[i] + 2.0 * k2[i] - 3544.0 / 2565.0 * k3[i]
                + 1859.0 / 4104.0 * k4[i]
                - 11.0 / 40.0 * k5[i]);
    }
    let mut k6 = [0.0f64; 8];
    unsafe {
        rhs(tmp.as_ptr(), t + dt * 0.5, p_ptr, p_len, k6.as_mut_ptr(), n as u32);
    }

    // 4th-order estimate
    let mut y4 = [0.0f64; 8];
    for i in 0..n {
        y4[i] = state.data[i]
            + dt * (25.0 / 216.0 * k1[i]
                + 1408.0 / 2565.0 * k3[i]
                + 2197.0 / 4104.0 * k4[i]
                - 0.2 * k5[i]);
    }

    // 5th-order estimate
    let mut y5 = [0.0f64; 8];
    for i in 0..n {
        y5[i] = state.data[i]
            + dt * (16.0 / 135.0 * k1[i]
                + 6656.0 / 12825.0 * k3[i]
                + 28561.0 / 56430.0 * k4[i]
                - 9.0 / 50.0 * k5[i]
                + 2.0 / 55.0 * k6[i]);
    }

    // Error estimate (max-norm scaled by tolerance)
    let mut err_max = 0.0f64;
    for i in 0..n {
        let err = (y5[i] - y4[i]).abs();
        let tol = atol + rtol * y5[i].abs();
        let ratio = err / tol;
        if ratio > err_max {
            err_max = ratio;
        }
    }

    // Accept/reject — pick final state, mutate state AFTER all k-borrows end.
    let mut chosen = [0.0f64; 8];
    if err_max <= 1.0 {
        chosen = y5;
    } else {
        for i in 0..n {
            chosen[i] = state.data[i];
        }
    }
    for i in 0..n {
        state.data[i] = chosen[i];
    }

    // Step-size control (PI controller)
    let safety = 0.9;
    let fac_min = 0.2;
    let fac_max = 5.0;
    let mut fac = safety * err_max.powf(-0.25);
    if fac < fac_min {
        fac = fac_min;
    }
    if fac > fac_max {
        fac = fac_max;
    }
    let mut dt_new = dt * fac;
    if dt_new > dt_max {
        dt_new = dt_max;
    }
    if dt_new < dt_min {
        dt_new = dt_min;
    }
    dt_new
}

/// Maximal Lyapunov exponent: ln(divergence rate) of perturbed trajectory.
pub fn lyapunov_estimate(
    rhs: OdeRHS,
    state: &StateVector,
    params: &[f64],
    shadow: &StateVector,
    t: f64,
) -> f64 {
    let n = state.len as usize;
    let mut d0 = 0.0f64;
    for i in 0..n {
        let diff = state.data[i] - shadow.data[i];
        d0 += diff * diff;
    }
    d0 = d0.sqrt();
    if d0 < 1e-12 {
        return 0.0;
    }

    let mut s = *shadow;
    rk4_step(rhs, &mut s, params, 0.01, t);
    let mut d1 = 0.0f64;
    for i in 0..n {
        let diff = state.data[i] - s.data[i];
        d1 += diff * diff;
    }
    d1 = d1.sqrt();
    if d1 < 1e-15 {
        return 0.0;
    }
    (d1 / d0).ln() / 0.01
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Harmonic oscillator: dy/dt = [v, -k*x]
    extern "C" fn harmonic(
        y: *const f64,
        _t: f64,
        params: *const f64,
        _params_len: u32,
        out: *mut f64,
        n: u32,
    ) {
        let k = unsafe { *params.add(0) };
        let y0 = unsafe { *y.add(0) };
        let y1 = unsafe { *y.add(1) };
        unsafe {
            *out.add(0) = y1;
            *out.add(1) = -k * y0;
        }
        let _ = n;
    }

    #[test]
    fn test_rk4_harmonic_dt_0_1() {
        let params = [1.0];
        let mut s = StateVector {
            data: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            len: 2,
        };
        rk4_step(harmonic, &mut s, &params, 0.1, 0.0);
        // cos(0.1) ≈ 0.995
        assert!(
            (0.9..=1.1).contains(&s.data[0]),
            "x = {} outside expected range",
            s.data[0]
        );
    }

    #[test]
    fn test_rk45_harmonic_stable() {
        let params = [1.0];
        let mut s = StateVector {
            data: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            len: 2,
        };
        let new_dt = rk45_step(
            harmonic, &mut s, &params, 0.0, 0.1, 1e-6, 1e-9, 1e-9, 1.0,
        );
        assert!(new_dt.is_finite());
        assert!(new_dt > 0.0);
    }
}
