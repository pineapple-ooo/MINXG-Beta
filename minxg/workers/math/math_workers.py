"""
MINXG Math Workers — Mathematical operations and analysis.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional


class CalculatorWorker:
    """Basic calculator with expression evaluation."""
    worker_id = "calculator"
    version = "0.19.0"

    def execute(self, expression: str) -> Dict[str, Any]:
        try:
            result = eval(expression, {"__builtins__": {}}, {
                "abs": abs, "round": round, "pow": pow,
                "min": min, "max": max, "sum": sum,
            })
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"error": str(e)}


class StatisticsWorker:
    """Statistical analysis."""
    worker_id = "statistics"
    version = "0.19.0"

    def execute(self, data: List[float]) -> Dict[str, Any]:
        import statistics
        if not data:
            return {"error": "Empty data"}

        return {
            "count": len(data),
            "mean": statistics.mean(data),
            "median": statistics.median(data),
            "mode": statistics.mode(data) if len(set(data)) < len(data) else None,
            "variance": statistics.variance(data) if len(data) > 1 else 0,
            "stdev": statistics.stdev(data) if len(data) > 1 else 0,
            "min": min(data),
            "max": max(data),
            "range": max(data) - min(data),
        }


class LinearAlgebraWorker:
    """Matrix operations."""
    worker_id = "linear_algebra"
    version = "0.19.0"

    def execute(self, matrix_a: List[List[float]], operation: str,
                matrix_b: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        try:
            import numpy as np
            A = np.array(matrix_a)

            if operation == "transpose":
                return {"result": A.T.tolist()}
            elif operation == "inverse":
                return {"result": np.linalg.inv(A).tolist()}
            elif operation == "determinant":
                return {"result": float(np.linalg.det(A))}
            elif operation == "eigenvalues":
                vals = np.linalg.eigvals(A)
                return {"eigenvalues": [float(v) if np.isreal(v) else complex(v) for v in vals]}
            elif operation == "rank":
                return {"rank": int(np.linalg.matrix_rank(A))}
            elif operation == "multiply" and matrix_b is not None:
                B = np.array(matrix_b)
                return {"result": (A @ B).tolist()}
            elif operation == "add" and matrix_b is not None:
                B = np.array(matrix_b)
                return {"result": (A + B).tolist()}
            else:
                return {"error": f"Unsupported operation: {operation}"}
        except ImportError:
            return {"error": "numpy required for linear algebra"}
        except Exception as e:
            return {"error": str(e)}


class CalculusWorker:
    """Derivatives and integrals."""
    worker_id = "calculus"
    version = "0.19.0"

    def execute(self, expression: str, variable: str = "x", point: Optional[float] = None,
                operation: str = "derivative") -> Dict[str, Any]:
        try:
            from sympy import symbols, diff, integrate, sympify, N

            x = symbols(variable)
            expr = sympify(expression)

            if operation == "derivative":
                result = diff(expr, x)
                if point is not None:
                    return {"derivative": str(result), "at_point": float(N(result.subs(x, point)))}
                return {"derivative": str(result)}
            elif operation == "integral":
                result = integrate(expr, x)
                return {"integral": str(result)}
            elif operation == "definite_integral":
                if point is None:
                    return {"error": "point required as lower bound, provide upper as well"}
                # Simple definite integral from 0 to point
                result = integrate(expr, (x, 0, point))
                return {"definite_integral": float(N(result))}
            else:
                return {"error": f"Unsupported operation: {operation}"}
        except ImportError:
            return {"error": "sympy required for calculus"}
        except Exception as e:
            return {"error": str(e)}


class FourierWorker:
    """Fourier transform."""
    worker_id = "fourier"
    version = "0.19.0"

    def execute(self, data: List[float]) -> Dict[str, Any]:
        try:
            import numpy as np
            fft_result = np.fft.fft(data)
            frequencies = np.fft.fftfreq(len(data))
            magnitudes = np.abs(fft_result)

            return {
                "fft": [complex(c) for c in fft_result[:20]],  # Limit output
                "magnitudes": magnitudes.tolist()[:20],
                "frequencies": frequencies.tolist()[:20],
                "length": len(data),
            }
        except ImportError:
            return {"error": "numpy required for FFT"}
        except Exception as e:
            return {"error": str(e)}


class PrimeWorker:
    """Prime number operations."""
    worker_id = "prime"
    version = "0.19.0"

    def execute(self, n: int, operation: str = "is_prime") -> Dict[str, Any]:
        def is_prime(num: int) -> bool:
            if num < 2:
                return False
            for i in range(2, int(num ** 0.5) + 1):
                if num % i == 0:
                    return False
            return True

        if operation == "is_prime":
            return {"n": n, "is_prime": is_prime(n)}
        elif operation == "factors":
            factors = []
            temp = n
            for i in range(2, int(n ** 0.5) + 1):
                while temp % i == 0:
                    factors.append(i)
                    temp //= i
            if temp > 1:
                factors.append(temp)
            return {"n": n, "factors": factors}
        elif operation == "nth_prime":
            count = 0
            candidate = 1
            while count < n:
                candidate += 1
                if is_prime(candidate):
                    count += 1
            return {"n": n, "nth_prime": candidate}
        elif operation == "primes_up_to":
            primes = []
            for i in range(2, n + 1):
                if is_prime(i):
                    primes.append(i)
            return {"up_to": n, "primes": primes, "count": len(primes)}
        else:
            return {"error": f"Unsupported operation: {operation}"}


class GeometryWorker:
    """Geometric calculations."""
    worker_id = "geometry"
    version = "0.19.0"

    def execute(self, shape: str, **kwargs) -> Dict[str, Any]:
        import math

        if shape == "circle":
            r = kwargs.get("radius", 1)
            return {
                "shape": "circle",
                "radius": r,
                "area": math.pi * r * r,
                "circumference": 2 * math.pi * r,
            }
        elif shape == "rectangle":
            w = kwargs.get("width", 1)
            h = kwargs.get("height", 1)
            return {
                "shape": "rectangle",
                "width": w,
                "height": h,
                "area": w * h,
                "perimeter": 2 * (w + h),
                "diagonal": math.sqrt(w * w + h * h),
            }
        elif shape == "triangle":
            a = kwargs.get("a", 1)
            b = kwargs.get("b", 1)
            c = kwargs.get("c", 1)
            s = (a + b + c) / 2
            area = math.sqrt(s * (s - a) * (s - b) * (s - c))
            return {
                "shape": "triangle",
                "sides": [a, b, c],
                "area": area,
                "perimeter": a + b + c,
                "semiperimeter": s,
            }
        elif shape == "sphere":
            r = kwargs.get("radius", 1)
            return {
                "shape": "sphere",
                "radius": r,
                "volume": (4/3) * math.pi * r**3,
                "surface_area": 4 * math.pi * r * r,
            }
        elif shape == "cylinder":
            r = kwargs.get("radius", 1)
            h = kwargs.get("height", 1)
            return {
                "shape": "cylinder",
                "radius": r,
                "height": h,
                "volume": math.pi * r * r * h,
                "surface_area": 2 * math.pi * r * (r + h),
            }
        else:
            return {"error": f"Unsupported shape: {shape}"}


class NumberTheoryWorker:
    """Number theory operations."""
    worker_id = "number_theory"
    version = "0.19.0"

    def execute(self, a: int, b: Optional[int] = None, operation: str = "gcd") -> Dict[str, Any]:
        import math

        if operation == "gcd":
            if b is None:
                return {"error": "gcd requires two numbers"}
            return {"a": a, "b": b, "gcd": math.gcd(a, b)}
        elif operation == "lcm":
            if b is None:
                return {"error": "lcm requires two numbers"}
            return {"a": a, "b": b, "lcm": abs(a * b) // math.gcd(a, b)}
        elif operation == "factorial":
            return {"n": a, "factorial": math.factorial(a)}
        elif operation == "fibonacci":
            if a <= 0:
                return {"error": "n must be positive"}
            fib = [0, 1]
            for i in range(2, a):
                fib.append(fib[-1] + fib[-2])
            return {"n": a, "fibonacci": fib, "nth": fib[-1] if fib else 0}
        elif operation == "modular_inverse":
            if b is None:
                return {"error": "modular_inverse requires modulus"}
            try:
                return {"a": a, "mod": b, "inverse": pow(a, -1, b)}
            except ValueError:
                return {"error": f"No modular inverse for {a} mod {b}"}
        else:
            return {"error": f"Unsupported operation: {operation}"}
