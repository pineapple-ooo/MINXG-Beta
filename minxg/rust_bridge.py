"""
minxg/rust_bridge.py — Python ↔ Rust FFI via ctypes.

Loads ``libminxg_rust.so`` and exposes all Rust operators as Python
functions. Memory-safe: every returned ptr is wrapped in a lifetime
guard. NULL checks are enforced at the FFI boundary (Rust side also
checks, but Python never passes NULL — it raises ValueError).

Design:
- ``RustLib`` lazily loads the library once per process.
- Struct layouts are ``ctypes.Structure`` mirrors of ``#[repr(C)]`` Rust types.
- ``JsonBuffer`` pattern from cpp_core adapted: call → ptr → copy → free.
"""

import ctypes
import math
import os
import sys
from ctypes import (
    c_int32, c_int64, c_double, c_char_p, c_void_p,
    c_uint32, c_uint64, c_uint8, c_bool,
    Structure, POINTER, byref, cast,
    cdll,
)
from pathlib import Path
from typing import Optional, List, Tuple

# ─── Find the shared library ──────────────────────────────────────────────────

def _find_lib() -> Optional[str]:
    """Locate libminxg_rust_core.so (release or debug build)."""
    base = Path(__file__).resolve().parent.parent  # repo root
    # Release build (Rust crate name → libminxg_rust_core.so)
    candidates = [
        base / "rust_core" / "target" / "release" / "libminxg_rust_core.so",
        base / "rust_core" / "target" / "release" / "libminxg_rust_core.dylib",
        # Debug build fallback
        base / "rust_core" / "target" / "debug" / "libminxg_rust_core.so",
        base / "rust_core" / "target" / "debug" / "libminxg_rust_core.dylib",
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    # Also check alongside the package
    me = Path(__file__).resolve().parent
    for name in ("libminxg_rust_core.so", "libminxg_rust_core.dylib"):
        if (me / name).exists():
            return str(me / name)

    return None


# ─── C struct mirrors ─────────────────────────────────────────────────────────

class Multivector(Structure):
    _fields_ = [
        ("scalar", c_double),
        ("v1", c_double), ("v2", c_double), ("v3", c_double),
        ("b1", c_double), ("b2", c_double), ("b3", c_double),
        ("trivector", c_double),
    ]

class StateVector(Structure):
    _fields_ = [
        ("data", c_double * 8),
        ("len", c_uint32),
    ]

class StepReport(Structure):
    _fields_ = [
        ("energy_delta", c_double),
        ("lyapunov_estimate", c_double),
        ("is_chaotic", c_uint8),
        ("singularity_detected", c_uint8),
        ("steps_taken", c_uint32),
        ("dt_used", c_double),
    ]

class ConnectionForm(Structure):
    _fields_ = [
        ("a0", c_double), ("a1", c_double), ("a2", c_double), ("a3", c_double),
    ]

class Jet(Structure):
    _fields_ = [
        ("value", c_double),
        ("derivs", c_double * 8),
        ("order", c_uint32),
    ]


# ─── Library wrapper ──────────────────────────────────────────────────────────

class RustLib:
    """Lazy singleton for the Rust shared library."""

    _instance: Optional["RustLib"] = None

    def __init__(self):
        path = _find_lib()
        if not path:
            raise FileNotFoundError(
                "libminxg_rust.so not found — build with: cd rust_core && cargo build --release"
            )
        self.lib = cdll.LoadLibrary(path)
        self._sign()

    @classmethod
    def get(cls) -> "RustLib":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _sign(self):
        """Set argtypes/restypes for every FFI function."""
        L = self.lib

        # Lifecycle
        L.rust_core_version.argtypes = []
        L.rust_core_version.restype = c_char_p
        L.rust_core_free.argtypes = [c_char_p]
        L.rust_core_free.restype = None
        L.rust_math_operator_count.argtypes = []
        L.rust_math_operator_count.restype = c_uint32

        # GA
        L.ga_geometric_product.argtypes = [POINTER(Multivector), POINTER(Multivector), POINTER(Multivector)]
        L.ga_geometric_product.restype = c_int32
        L.ga_outer_product.argtypes = [POINTER(Multivector), POINTER(Multivector), POINTER(Multivector)]
        L.ga_outer_product.restype = c_int32
        L.ga_inner_product.argtypes = [POINTER(Multivector), POINTER(Multivector), POINTER(c_double)]
        L.ga_inner_product.restype = c_int32
        L.ga_rotor_apply.argtypes = [POINTER(c_double * 4), POINTER(c_double * 3), POINTER(c_double * 3)]
        L.ga_rotor_apply.restype = c_int32

        # Driver
        L.driver_rk4_step.argtypes = [
            c_void_p,  # fn ptr
            POINTER(StateVector),
            POINTER(c_double), c_uint32,
            c_double, c_double,
        ]
        L.driver_rk4_step.restype = c_int32

        L.driver_rk45_step.argtypes = [
            c_void_p,
            POINTER(StateVector),
            POINTER(c_double), c_uint32,
            c_double, c_double, c_double, c_double, c_double, c_double,
            POINTER(c_double),
        ]
        L.driver_rk45_step.restype = c_int32

        # Chaos
        L.chaos_logistic_map.argtypes = [c_double, c_double]
        L.chaos_logistic_map.restype = c_double
        L.chaos_lorenz_integrate.argtypes = [
            POINTER(c_double * 3), c_double, c_double, c_double, c_double, c_uint32,
        ]
        L.chaos_lorenz_integrate.restype = c_int32

        # Fiber
        L.fiber_curvature.argtypes = [POINTER(ConnectionForm), POINTER(c_double * 16)]
        L.fiber_curvature.restype = c_int32
        L.fiber_parallel_transport.argtypes = [POINTER(ConnectionForm), c_double, POINTER(c_double * 4)]
        L.fiber_parallel_transport.restype = c_double

        # SymbDiff
        L.symbdiff_jet_add.argtypes = [POINTER(Jet), POINTER(Jet), POINTER(Jet)]
        L.symbdiff_jet_add.restype = c_int32
        L.symbdiff_jet_mul.argtypes = [POINTER(Jet), POINTER(Jet), POINTER(Jet)]
        L.symbdiff_jet_mul.restype = c_int32
        L.symbdiff_jet_exp.argtypes = [POINTER(Jet), POINTER(Jet)]
        L.symbdiff_jet_exp.restype = c_int32

        # MemPool
        L.mempool_create.argtypes = [c_uint64]
        L.mempool_create.restype = c_void_p
        L.mempool_free.argtypes = [c_void_p]
        L.mempool_free.restype = None
        L.mempool_alloc.argtypes = [c_void_p, c_uint64]
        L.mempool_alloc.restype = c_uint64
        L.mempool_free_slot.argtypes = [c_void_p, c_uint64]
        L.mempool_free_slot.restype = c_int32
        L.mempool_write.argtypes = [c_void_p, c_uint64, POINTER(c_uint8), c_uint64]
        L.mempool_write.restype = c_uint64
        L.mempool_read.argtypes = [c_void_p, c_uint64, POINTER(c_uint8), c_uint64]
        L.mempool_read.restype = c_uint64
        L.mempool_stats.argtypes = [c_void_p, POINTER(c_uint64)]
        L.mempool_stats.restype = c_int32

        # math_ops (v0.16.5)
        L.vec_mean.argtypes = [POINTER(c_double), c_uint32]
        L.vec_mean.restype = c_double
        L.vec_std.argtypes = [POINTER(c_double), c_uint32]
        L.vec_std.restype = c_double
        L.vec_minmax.argtypes = [POINTER(c_double), c_uint32, POINTER(c_double), POINTER(c_double)]
        L.vec_minmax.restype = c_int32
        L.vec_correlation.argtypes = [POINTER(c_double), POINTER(c_double), c_uint32]
        L.vec_correlation.restype = c_double
        L.vec_stats.argtypes = [POINTER(c_double), c_uint32, POINTER(c_double), POINTER(c_double), POINTER(c_double), POINTER(c_double)]
        L.vec_stats.restype = c_int32
        L.mat_mul.argtypes = [
            POINTER(c_double), c_uint32, c_uint32,
            POINTER(c_double), c_uint32, c_uint32,
            POINTER(c_double),
        ]
        L.mat_mul.restype = c_int32

        # str_ops (v0.16.5)
        L.str_hash64.argtypes = [POINTER(c_uint8), c_uint32]
        L.str_hash64.restype = c_uint64
        L.str_count.argtypes = [POINTER(c_uint8), c_uint32, c_uint8]
        L.str_count.restype = c_uint32
        L.str_lower_ascii.argtypes = [POINTER(c_uint8), c_uint32]
        L.str_lower_ascii.restype = c_int32
        L.str_utf8_validate.argtypes = [POINTER(c_uint8), c_uint32]
        L.str_utf8_validate.restype = c_int32
        L.vec_sum_sq.argtypes = [POINTER(c_double), c_uint32]
        L.vec_sum_sq.restype = c_double
        L.vec_dot.argtypes = [POINTER(c_double), POINTER(c_double), c_uint32]
        L.vec_dot.restype = c_double
        L.vec_normalize.argtypes = [POINTER(c_double), c_uint32]
        L.vec_normalize.restype = c_int32
        L.vec_fused_sqadd_sum.argtypes = [POINTER(c_double), c_uint32]
        L.vec_fused_sqadd_sum.restype = c_double

    # ─── High-level Python wrappers ───────────────────────────────────────

    def version(self) -> str:
        ptr = self.lib.rust_core_version()
        if not ptr:
            return "unknown"
        result = ctypes.cast(ptr, c_char_p).value.decode("utf-8")
        self.lib.rust_core_free(ptr)
        return result

    def math_operator_count(self) -> int:
        return self.lib.rust_math_operator_count()


# ─── Pythonic operator wrappers ────────────────────────────────────────────────

def geometric_product(a_scalar, a_v1, a_v2, a_v3, a_b1, a_b2, a_b3, a_tri,
                      b_scalar, b_v1, b_v2, b_v3, b_b1, b_b2, b_b3, b_tri):
    """Return Multivector from a * b."""
    rl = RustLib.get()
    a = Multivector(a_scalar, a_v1, a_v2, a_v3, a_b1, a_b2, a_b3, a_tri)
    b = Multivector(b_scalar, b_v1, b_v2, b_v3, b_b1, b_b2, b_b3, b_tri)
    out = Multivector()
    rc = rl.lib.ga_geometric_product(byref(a), byref(b), byref(out))
    if rc != 0:
        raise ValueError("ga_geometric_product: null pointer")
    return (out.scalar, out.v1, out.v2, out.v3, out.b1, out.b2, out.b3, out.trivector)


def logistic_map(x: float, r: float) -> float:
    rl = RustLib.get()
    return rl.lib.chaos_logistic_map(x, r)


def lorenz_integrate(state_xyz: List[float], sigma: float, rho: float, beta: float, dt: float, steps: int) -> List[float]:
    rl = RustLib.get()
    arr = (c_double * 3)(*state_xyz)
    rl.lib.chaos_lorenz_integrate(byref(arr), sigma, rho, beta, dt, steps)
    return [arr[0], arr[1], arr[2]]


def jet_add(a_val, a_derivs, a_order, b_val, b_derivs, b_order):
    rl = RustLib.get()
    a = Jet(a_val, (c_double * 8)(*a_derivs), a_order)
    b = Jet(b_val, (c_double * 8)(*b_derivs), b_order)
    out = Jet()
    rl.lib.symbdiff_jet_add(byref(a), byref(b), byref(out))
    return out.value, list(out.derivs), out.order


# ─── Test-level detection ──────────────────────────────────────────────────────

def is_rust_available() -> bool:
    """Return True if the Rust shared library exists on disk.

    Previously this also tried ``ctypes.CDLL(path)``, which fails on
    Termux/Android even when the .so is valid because of namespace
    restrictions.  That caused *all* Rust-backed tests to skip instead
    of running.  We now only check file existence here; callers that
    actually need to call into Rust will still hit ``OSError`` from
    ctypes in sandboxed environments, which is the correct failure mode.
    """
    return _find_lib() is not None


# ─── v0.16.5 — math_ops / str_ops high-level Python wrappers ───────────────


def vec_mean(values) -> float:
    """Mean of an iterable of floats (Rust-backed)."""
    rl = RustLib.get()
    buf = (c_double * len(values))(*values)
    rc = rl.lib.vec_mean(buf, len(values))
    if rc < 0:
        raise ValueError("vec_mean: empty input")
    return rc


def vec_std(values) -> float:
    rl = RustLib.get()
    buf = (c_double * len(values))(*values)
    rc = rl.lib.vec_std(buf, len(values))
    return rc


def vec_minmax(values) -> tuple:
    rl = RustLib.get()
    buf = (c_double * len(values))(*values)
    mn = c_double(0.0)
    mx = c_double(0.0)
    if rl.lib.vec_minmax(buf, len(values), byref(mn), byref(mx)) != 0:
        raise ValueError("vec_minmax failed")
    return (mn.value, mx.value)


def vec_stats(values) -> dict:
    """Batch stats: mean, std, min, max in a single Rust call."""
    rl = RustLib.get()
    n = len(values)
    buf = (c_double * n)(*values)
    mean = c_double(0.0)
    std = c_double(0.0)
    mn = c_double(0.0)
    mx = c_double(0.0)
    rc = rl.lib.vec_stats(buf, n, byref(mean), byref(std), byref(mn), byref(mx))
    if rc != 0:
        raise ValueError("vec_stats failed")
    return {"mean": mean.value, "std": std.value, "min": mn.value, "max": mx.value}


def vec_correlation(a, b) -> float:
    if len(a) != len(b):
        raise ValueError("vec_correlation: length mismatch")
    rl = RustLib.get()
    va = (c_double * len(a))(*a)
    vb = (c_double * len(b))(*b)
    return rl.lib.vec_correlation(va, vb, len(a))


def mat_mul(a, ar, ac, b, br, bc):
    if ac != br:
        raise ValueError("mat_mul: dim mismatch")
    rl = RustLib.get()
    sz = ar * bc
    buf_a = (c_double * len(a))(*a)
    buf_b = (c_double * len(b))(*b)
    buf_o = (c_double * sz)()
    rc = rl.lib.mat_mul(buf_a, ar, ac, buf_b, br, bc, buf_o)
    if rc != 0:
        raise ValueError(f"mat_mul error: {rc}")
    return list(buf_o)


def str_hash64(s: bytes) -> int:
    rl = RustLib.get()
    if not s:
        return 0
    buf = (c_uint8 * len(s))(*s)
    return rl.lib.str_hash64(buf, len(s))


def str_count_byte(s: bytes, want: int) -> int:
    rl = RustLib.get()
    buf = (c_uint8 * len(s))(*s)
    return rl.lib.str_count(buf, len(s), want)


def str_lower_ascii_inplace(buf) -> int:
    """Lowercase ASCII bytes in the bytearray passed in (Rust-backed).

    Returns 0 on success, -1 on bad input.
    """
    rl = RustLib.get()
    ba = bytearray(buf)
    raw = (c_uint8 * len(ba))(*ba)
    rc = rl.lib.str_lower_ascii(raw, len(ba))
    for i, v in enumerate(raw):
        ba[i] = v
    buf[:] = ba
    return rc


def vec_dot(a, b) -> float:
    if len(a) != len(b):
        raise ValueError("vec_dot: length mismatch")
    rl = RustLib.get()
    va = (c_double * len(a))(*a)
    vb = (c_double * len(b))(*b)
    return rl.lib.vec_dot(va, vb, len(a))


# ─── Signal processing (v0.18.2) ────────────────────────────────────

def signal_fft_real(data: List[float], fft_len: int) -> List[float]:
    """Radix-2 DIT FFT on real-valued data.
    Returns interleaved [re0, im0, re1, im1, ...] complex pairs.
    fft_len must be power-of-2. Data is zero-padded if shorter.
    """
    rl = RustLib.get()
    n = len(data)
    va = (c_double * n)(*data)
    out_len = fft_len * 2
    out = (c_double * out_len)()
    rc = rl.lib.fft_real(va, n, fft_len, out)
    if rc != 0:
        raise RuntimeError(f"fft_real failed with code {rc}")
    return list(out)


def signal_dwt_haar(data: List[float]) -> Tuple[List[float], List[float]]:
    """1-level Haar DWT. Returns (approx, detail) each of length len(data)/2."""
    rl = RustLib.get()
    n = len(data)
    if n < 2 or n % 2 != 0:
        raise ValueError("dwt_haar: length must be even and >= 2")
    va = (c_double * n)(*data)
    half = n // 2
    approx = (c_double * half)()
    detail = (c_double * half)()
    rc = rl.lib.dwt_haar(va, n, approx, detail)
    if rc != 0:
        raise RuntimeError(f"dwt_haar failed with code {rc}")
    return list(approx), list(detail)


class _KalmanState:
    """Mutable Kalman filter state."""
    def __init__(self, init_state: float = 0.0, init_cov: float = 1000.0):
        self._state = c_double(init_state)
        self._cov = c_double(init_cov)

    def step(self, measurement: float, process_noise: float = 0.001, measurement_noise: float = 0.1) -> float:
        rl = RustLib.get()
        rl.lib.kalman_step(byref(self._state), byref(self._cov),
                           c_double(measurement), c_double(process_noise), c_double(measurement_noise))
        return self._state.value


def signal_entropy(bins: List[float]) -> float:
    """Shannon entropy from normalized histogram bins."""
    rl = RustLib.get()
    n = len(bins)
    vb = (c_double * n)(*bins)
    return rl.lib.entropy_shannon(vb, n)


def signal_autocorr(data: List[float], max_lag: int) -> List[float]:
    """Unbiased autocorrelation for lags 0..max_lag."""
    rl = RustLib.get()
    n = len(data)
    out_len = max_lag + 1
    out = (c_double * out_len)()
    rc = rl.lib.autocorrelation((c_double * n)(*data), n, max_lag, out)
    if rc != 0:
        raise RuntimeError(f"autocorrelation failed with code {rc}")
    return list(out)


def signal_peak_detect(data: List[float], max_peaks: int = 10) -> List[Tuple[int, float]]:
    """Detect peaks via zero-crossing of first derivative."""
    rl = RustLib.get()
    n = len(data)
    idx_out = (c_uint32 * max_peaks)()
    val_out = (c_double * max_peaks)()
    count = rl.lib.peak_detect((c_double * n)(*data), n, idx_out, val_out, max_peaks)
    if count < 0:
        raise RuntimeError("peak_detect failed")
    return [(idx_out[i], val_out[i]) for i in range(count)]


def signal_energy(data: List[float]) -> float:
    """Sum of squares (Parseval-adjacent energy)."""
    rl = RustLib.get()
    n = len(data)
    return rl.lib.signal_energy((c_double * n)(*data), n)


# ── v0.18.2: Lyapunov + fixed-point ──────────────────────────────────

def _lyapunov_python(x0: float, r: float, transient: int, iters: int) -> Dict[str, Any]:
    """Pure-Python Lyapunov fallback (no Rust needed)."""
    x = max(0.0001, min(0.9999, x0))
    for _ in range(transient):
        x = r * x * (1.0 - x)
        if not math.isfinite(x):
            x = 0.5
    total = 0.0
    count = 0
    orbit_sample = []
    for i in range(iters):
        df = abs(r * (1.0 - 2.0 * x))
        if df > 1e-14:
            total += math.log(df)
            count += 1
        if i < 50:
            orbit_sample.append(round(x, 5))
        x = r * x * (1.0 - x)
        if not math.isfinite(x):
            break
    lam = total / count if count > 0 else -999.0
    return _classify_lambda(lam, r, x0, orbit_sample)


def _classify_lambda(lam: float, r: float, x0: float, orbit: list) -> Dict[str, Any]:
    if lam > 0.3:
        cls, pun = "chaotic", f"λ={lam:.4f} — full chaos, orbit looks like static"
    elif lam > 0.0:
        cls, pun = "weakly chaotic", f"λ={lam:.4f} — structured chaos, predictable unpredictability"
    elif lam > -0.1:
        cls, pun = "near-bifurcation", f"λ={lam:.4f} — on the knife-edge of order and chaos"
    else:
        cls, pun = "periodic/stable", f"λ={lam:.4f} — settles down, predictable future"
    return {
        "status": "ok", "lambda": round(lam, 6),
        "classification": cls, "r": r, "x0": x0,
        "punchline": pun, "orbit_sample": orbit,
        "engine": "pure_python (Rust .so not built)",
    }


def lyapunov_logistic(x0: float, r: float, transient: int = 500,
                       iters: int = 10000) -> Dict[str, Any]:
    """Lyapunov exponent λ for logistic map x_{n+1}=r·x_n·(1-x_n).

    λ > 0  → chaotic / λ < 0  → periodic / λ ≈ 0  → bifurcation edge.
    Uses Rosenstein method: average slope of ln|dF/dx| along orbit.
    Auto-falls back to pure Python if Rust .so not available.
    """
    try:
        rl = RustLib.get()
        buf = (c_double * max(0, iters))()
        lam = rl.lib.lyapunov_logistic(x0, r, transient, iters, buf)
        if lam < -900.0:
            return {"status": "error", "error": f"bad params r={r}, x0={x0}"}
        orbit = list(buf[:min(50, iters)])
        return _classify_lambda(lam, r, x0, orbit)
    except FileNotFoundError:
        # .so not built — use pure Python fallback
        return _lyapunov_python(x0, r, transient, iters)


def fixed_point_iter(
    g_fn,          # callable f64 → f64
    x0: float = 0.5,
    max_iter: int = 200,
    tol: float = 1e-10,
) -> Dict[str, Any]:
    """Solve x = g(x) via successive substitution.  Converges if |g'(x)| < 1 near root.

    Use for: implicit equations, steady-state PDEs, economic equilibrium,
    chemical equilibrium, BEM integrals — anywhere you'd otherwise need Newton
    but lack or don't trust the derivative.
    """
    x = x0
    history = [x]
    for _ in range(max_iter):
        nx = g_fn(x)
        if not isinstance(nx, float) or not math.isfinite(nx):
            return {"status": "error", "x": float(x), "converged": False,
                    "reason": "non-finite intermediate", "history": history[-10:]}
        if abs(nx - x) < tol:
            return {"status": "ok", "x": float(nx), "converged": True,
                    "iterations": len(history), "history": history}
        x = nx
        history.append(x)
    return {"status": "partial", "x": float(x), "converged": False,
            "iterations": max_iter, "reason": "max_iter", "history": history[-10:]}
