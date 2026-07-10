//! C FFI exports — all functions exposed with `extern "C"` for ctypes/cffi.
//!
//! Memory ownership: every function returning a pointer allocates with Rust's
//! allocator. Python must call `rust_core_free(ptr)` to release. No leaks.
//!
//! Struct layouts are `#[repr(C)]`, identical to definitions in each module.

use std::ffi::CString;
use std::os::raw::c_char;

use crate::{
    chaos,
    driver::{self, StateVector},
    fiber::{self, ConnectionForm},
    ga::{self, Multivector},
    symbdiff::{self, Jet},
};

// ─── Lifecycle ────────────────────────────────────────────────────────────────

/// Return the crate version as a C string (caller must free).
#[no_mangle]
pub extern "C" fn rust_core_version() -> *mut c_char {
    let s = CString::new(crate::VERSION).unwrap();
    s.into_raw()
}

/// Free a C string or buffer allocated by this crate.
#[no_mangle]
pub extern "C" fn rust_core_free(ptr: *mut c_char) {
    if ptr.is_null() { return; }
    unsafe { drop(CString::from_raw(ptr)); }
}

/// Return Rust math operator count.
#[no_mangle]
pub extern "C" fn rust_math_operator_count() -> u32 {
    crate::RUST_MATH_OPERATORS
}

// ─── Geometric Algebra ────────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn ga_geometric_product(a: *const Multivector, b: *const Multivector, out: *mut Multivector) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() { return -1; }
    unsafe {
        *out = ga::geometric_product(&*a, &*b);
    }
    0
}

#[no_mangle]
pub extern "C" fn ga_outer_product(a: *const Multivector, b: *const Multivector, out: *mut Multivector) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() { return -1; }
    unsafe {
        *out = ga::outer_product(&*a, &*b);
    }
    0
}

#[no_mangle]
pub extern "C" fn ga_inner_product(a: *const Multivector, b: *const Multivector, out: *mut f64) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() { return -1; }
    unsafe {
        *out = ga::inner_product(&*a, &*b);
    }
    0
}

#[no_mangle]
pub extern "C" fn ga_rotor_apply(
    rotor: *const [f64; 4],
    vector: *const [f64; 3],
    out: *mut [f64; 3],
) -> i32 {
    if rotor.is_null() || vector.is_null() || out.is_null() { return -1; }
    unsafe {
        *out = ga::rotor_apply(&*rotor, &*vector);
    }
    0
}

// ─── Driver Engine ────────────────────────────────────────────────────────────

/// RK4 fixed-step integration.
/// `rhs` is a function pointer matching OdeRHS signature.
#[no_mangle]
pub extern "C" fn driver_rk4_step(
    rhs: driver::OdeRHS,
    state: *mut StateVector,
    params: *const f64,
    params_len: u32,
    dt: f64,
    t: f64,
) -> i32 {
    if state.is_null() || params.is_null() { return -1; }
    unsafe {
        let params_slice = std::slice::from_raw_parts(params, params_len as usize);
        driver::rk4_step(rhs, &mut *state, params_slice, dt, t);
    }
    0
}

/// RK45 adaptive-step integration. Returns new dt.
#[no_mangle]
pub extern "C" fn driver_rk45_step(
    rhs: driver::OdeRHS,
    state: *mut StateVector,
    params: *const f64,
    params_len: u32,
    t: f64,
    dt: f64,
    rtol: f64,
    atol: f64,
    dt_min: f64,
    dt_max: f64,
    out_dt: *mut f64,
) -> i32 {
    if state.is_null() || params.is_null() || out_dt.is_null() { return -1; }
    unsafe {
        let params_slice = std::slice::from_raw_parts(params, params_len as usize);
        *out_dt = driver::rk45_step(rhs, &mut *state, params_slice, t, dt, rtol, atol, dt_min, dt_max);
    }
    0
}

// ─── Chaos ────────────────────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn chaos_logistic_map(x: f64, r: f64) -> f64 {
    chaos::logistic_map(x, r)
}

#[no_mangle]
pub extern "C" fn chaos_lorenz_integrate(
    state: *mut [f64; 3],
    sigma: f64, rho: f64, beta: f64,
    dt: f64, steps: u32,
) -> i32 {
    if state.is_null() { return -1; }
    unsafe {
        chaos::lorenz_integrate(&mut *state, sigma, rho, beta, dt, steps);
    }
    0
}

// ─── Fiber Bundles ────────────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn fiber_curvature(
    conn: *const ConnectionForm,
    out: *mut [f64; 16],
) -> i32 {
    if conn.is_null() || out.is_null() { return -1; }
    unsafe {
        fiber::curvature(&*conn, &mut *out);
    }
    0
}

#[no_mangle]
pub extern "C" fn fiber_parallel_transport(
    conn: *const ConnectionForm,
    section_value: f64,
    dx: *const [f64; 4],
) -> f64 {
    if conn.is_null() || dx.is_null() { return 0.0; }
    unsafe {
        fiber::parallel_transport(&*conn, section_value, &*dx)
    }
}

// ─── SymbDiff ─────────────────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn symbdiff_jet_add(a: *const Jet, b: *const Jet, out: *mut Jet) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() { return -1; }
    unsafe { *out = symbdiff::jet_add(&*a, &*b); }
    0
}

#[no_mangle]
pub extern "C" fn symbdiff_jet_mul(a: *const Jet, b: *const Jet, out: *mut Jet) -> i32 {
    if a.is_null() || b.is_null() || out.is_null() { return -1; }
    unsafe { *out = symbdiff::jet_mul(&*a, &*b); }
    0
}

#[no_mangle]
pub extern "C" fn symbdiff_jet_exp(f: *const Jet, out: *mut Jet) -> i32 {
    if f.is_null() || out.is_null() { return -1; }
    unsafe { *out = symbdiff::jet_exp(&*f); }
    0
}

#[no_mangle]
pub extern "C" fn symbdiff_lie_bracket(
    x: *const f64, y: *const f64,
    dim: u32,
    out: *mut f64,
) -> i32 {
    if x.is_null() || y.is_null() || out.is_null() { return -1; }
    unsafe {
        let x_slice = std::slice::from_raw_parts(x, dim as usize);
        let y_slice = std::slice::from_raw_parts(y, dim as usize);
        let out_slice = std::slice::from_raw_parts_mut(out, dim as usize);
        symbdiff::lie_bracket(x_slice, y_slice, dim as usize, out_slice);
    }
    0
}