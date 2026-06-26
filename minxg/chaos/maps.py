"""
minxg/chaos/maps.py — Classic Discrete and Continuous Dynamical Systems
================================================================================

THE LOGISTIC MAP
----------------
x_{n+1} = r · x_n · (1 - x_n)

The canonical example of period-doubling bifurcation and chaos.
- r ∈ [0, 3]: fixed point attractor
- r ∈ [3, 1+√6]: period-2 cycle
- r ∈ [3.449..., 3.544...]: period-4 → period-8 → chaos
- Feigenbaum constant δ ≈ 4.6692016...

THE HENON MAP
-------------
(x, y)_{n+1} = (1 - a·x_n² + y_n, b·x_n)

THE LORENZ SYSTEM (continuous)
------------------------------
dx/dt = σ(y - x)
dy/dt = x(ρ - z) - y
dz/dt = xy - βz

THE ROSSLER SYSTEM
------------------
dx/dt = -y - z
dy/dt = x + a·y
dz/dt = b + z(x - c)

THE DUFFING OSCILLATOR
----------------------
d²x/dt² + δ·dx/dt + α·x + β·x³ = γ·cos(ω·t)
"""
from __future__ import annotations
import math
from typing import Callable, List, Tuple


def logistic_map(r: float, x0: float, n: int) -> List[float]:
    """Iterate the logistic map x_{n+1} = r·x_n·(1-x_n)."""
    out = [x0]
    x = x0
    for _ in range(n):
        x = r * x * (1 - x)
        out.append(x)
    return out


def henon_map(a: float, b: float, x0: float, y0: float, n: int) -> List[Tuple[float, float]]:
    """Iterate the Henon map (x, y)_{n+1} = (1 - a·x² + y, b·x)."""
    out = [(x0, y0)]
    x, y = x0, y0
    for _ in range(n):
        nx = 1 - a * x * x + y
        ny = b * x
        x, y = nx, ny
        out.append((x, y))
    return out


def lorenz(sigma: float, rho: float, beta: float,
           x0: float, y0: float, z0: float,
           dt: float = 0.01, n: int = 10000) -> List[Tuple[float, float, float]]:
    """Integrate the Lorenz system using RK4.

    The famous "butterfly attractor" with σ=10, ρ=28, β=8/3.
    """
    out = [(x0, y0, z0)]
    x, y, z = x0, y0, z0
    for _ in range(n):
        k1x = sigma * (y - x)
        k1y = x * (rho - z) - y
        k1z = x * y - beta * z

        k2x = sigma * (y + 0.5 * dt * k1y - (x + 0.5 * dt * k1x))
        k2y = (x + 0.5 * dt * k1x) * (rho - (z + 0.5 * dt * k1z)) - (y + 0.5 * dt * k1y)
        k2z = (x + 0.5 * dt * k1x) * (y + 0.5 * dt * k1y) - beta * (z + 0.5 * dt * k1z)

        k3x = sigma * (y + 0.5 * dt * k2y - (x + 0.5 * dt * k2x))
        k3y = (x + 0.5 * dt * k2x) * (rho - (z + 0.5 * dt * k2z)) - (y + 0.5 * dt * k2y)
        k3z = (x + 0.5 * dt * k2x) * (y + 0.5 * dt * k2y) - beta * (z + 0.5 * dt * k2z)

        k4x = sigma * (y + dt * k3y - (x + dt * k3x))
        k4y = (x + dt * k3x) * (rho - (z + dt * k3z)) - (y + dt * k3y)
        k4z = (x + dt * k3x) * (y + dt * k3y) - beta * (z + dt * k3z)

        x = x + dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
        y = y + dt / 6 * (k1y + 2 * k2y + 2 * k3y + k4y)
        z = z + dt / 6 * (k1z + 2 * k2z + 2 * k3z + k4z)
        out.append((x, y, z))
    return out


def rossler(a: float, b: float, c: float,
            x0: float, y0: float, z0: float,
            dt: float = 0.01, n: int = 10000) -> List[Tuple[float, float, float]]:
    """Integrate the Rossler system using RK4."""
    out = [(x0, y0, z0)]
    x, y, z = x0, y0, z0
    for _ in range(n):
        k1x = -y - z
        k1y = x + a * y
        k1z = b + z * (x - c)

        k2x = -(y + 0.5 * dt * k1y) - (z + 0.5 * dt * k1z)
        k2y = (x + 0.5 * dt * k1x) + a * (y + 0.5 * dt * k1y)
        k2z = b + (z + 0.5 * dt * k1z) * ((x + 0.5 * dt * k1x) - c)

        k3x = -(y + 0.5 * dt * k2y) - (z + 0.5 * dt * k2z)
        k3y = (x + 0.5 * dt * k2x) + a * (y + 0.5 * dt * k2y)
        k3z = b + (z + 0.5 * dt * k2z) * ((x + 0.5 * dt * k2x) - c)

        k4x = -(y + dt * k3y) - (z + dt * k3z)
        k4y = (x + dt * k3x) + a * (y + dt * k3y)
        k4z = b + (z + dt * k3z) * ((x + dt * k3x) - c)

        x = x + dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
        y = y + dt / 6 * (k1y + 2 * k2y + 2 * k3y + k4y)
        z = z + dt / 6 * (k1z + 2 * k2z + 2 * k3z + k4z)
        out.append((x, y, z))
    return out


def duffing(delta: float, alpha: float, beta: float,
            gamma: float, omega: float,
            x0: float, v0: float, t0: float = 0.0,
            dt: float = 0.01, n: int = 10000) -> List[Tuple[float, float]]:
    """Integrate the Duffing oscillator.

    d²x/dt² + δ·dx/dt + α·x + β·x³ = γ·cos(ω·t)
    """
    out = [(t0, x0, v0)]
    x, v, t = x0, v0, t0
    for _ in range(n):
        a_x = v
        a_v = gamma * math.cos(omega * t) - delta * v - alpha * x - beta * x ** 3
        
        x_mid = x + 0.5 * dt * a_x
        v_mid = v + 0.5 * dt * a_v
        t_mid = t + 0.5 * dt
        a_x2 = v_mid
        a_v2 = gamma * math.cos(omega * t_mid) - delta * v_mid - alpha * x_mid - beta * x_mid ** 3
        x = x + dt * a_x2
        v = v + dt * a_v2
        t = t + dt
        out.append((t, x, v))
    return out
