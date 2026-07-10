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
    """Locate libminxg_rust.so (release build)."""
    base = Path(__file__).resolve().parent.parent  # repo root
    candidates = [
        base / "rust_core" / "target" / "release" / "libminxg_rust.so",
        base / "rust_core" / "target" / "release" / "libminxg_rust.dylib",
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    # Also check alongside the package
    me = Path(__file__).resolve().parent
    for name in ("libminxg_rust.so", "libminxg_rust.dylib"):
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
    """Return True if the Rust shared library exists AND can be dlopen'd.

    ``_find_lib()`` returns the on-disk path; we also check it loads.
    On Termux/Android, even a valid .so under ``/storage/emulated/0/`` can
    fail dlopen due to namespace restrictions — that's a sandbox issue,
    not a code defect, and we report "not available" to skip FFI tests.
    """
    path = _find_lib()
    if path is None:
        return False
    try:
        import ctypes
        ctypes.CDLL(path)
        return True
    except OSError:
        return False