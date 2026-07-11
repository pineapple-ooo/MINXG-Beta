"""
math_adv.py — Advanced Math Operators 

100+ operators covering: bitwise, advanced math, statistics, sequences,
matrix-like ops, complex numbers, big integers. IDs: 100-449.
All implemented in pure stdlib (math, cmath, functools, itertools, fractions).
"""

from __future__ import annotations
import math
import cmath
import fractions
import itertools
import functools
import re
from typing import Dict, List, Any, Tuple
from minxg.base import BaseWorker, tool


class MathAdvWorker(BaseWorker):
    facade_alias = "math_tools"
    worker_id = "math_adv"
    version = "0.17.1"

    # ══════════════════════════════════════════════════════════════════════════
    # BITWISE (IDs 100-149)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Bitwise AND of two integers", category="bitwise")
    async def bitwise_and(self, a: int, b: int) -> Dict:
        return {"result": a & b, "operation": "and", "a": a, "b": b, "binary": bin(a & b)}

    @tool(description="Bitwise OR of two integers", category="bitwise")
    async def bitwise_or(self, a: int, b: int) -> Dict:
        return {"result": a | b, "operation": "or", "a": a, "b": b, "binary": bin(a | b)}

    @tool(description="Bitwise XOR of two integers", category="bitwise")
    async def bitwise_xor(self, a: int, b: int) -> Dict:
        return {"result": a ^ b, "operation": "xor", "a": a, "b": b, "binary": bin(a ^ b)}

    @tool(description="Bitwise NOT (invert all bits)", category="bitwise")
    async def bitwise_not(self, a: int, bits: int = 32) -> Dict:
        mask = (1 << bits) - 1
        return {"result": (~a) & mask, "operation": "not", "a": a, "bits": bits, "binary": bin((~a) & mask)}

    @tool(description="Shift left by n bits", category="bitwise")
    async def shift_left(self, a: int, n: int) -> Dict:
        return {"result": a << n, "operation": "shift_left", "a": a, "n": n, "binary": bin(a << n)}

    @tool(description="Shift right by n bits", category="bitwise")
    async def shift_right(self, a: int, n: int) -> Dict:
        return {"result": a >> n, "operation": "shift_right", "a": a, "n": n, "binary": bin(a >> n)}

    @tool(description="Rotate left by n bits within width bits", category="bitwise")
    async def rotate_left(self, a: int, n: int, width: int = 32) -> Dict:
        mask = (1 << width) - 1
        a &= mask
        return {"result": ((a << n) | (a >> (width - n))) & mask, "operation": "rotate_left", "a": a, "n": n, "width": width}

    @tool(description="Rotate right by n bits within width bits", category="bitwise")
    async def rotate_right(self, a: int, n: int, width: int = 32) -> Dict:
        mask = (1 << width) - 1
        a &= mask
        return {"result": ((a >> n) | (a << (width - n))) & mask, "operation": "rotate_right", "a": a, "n": n, "width": width}

    @tool(description="Count bits set to 1 (population count)", category="bitwise")
    async def count_bits(self, a: int) -> Dict:
        return {"result": bin(a).count('1'), "operation": "count_bits", "a": a}

    @tool(description="Check parity (1 if odd number of 1-bits)", category="bitwise")
    async def parity(self, a: int) -> Dict:
        return {"result": bin(a).count('1') % 2, "operation": "parity", "a": a}

    @tool(description="Number of bits needed to represent a", category="bitwise")
    async def bit_length_op(self, a: int) -> Dict:
        return {"result": a.bit_length(), "operation": "bit_length", "a": a}

    @tool(description="Get specific bit at position n (0=LSB)", category="bitwise")
    async def get_bit(self, a: int, n: int) -> Dict:
        return {"result": (a >> n) & 1, "operation": "get_bit", "a": a, "position": n}

    @tool(description="Set bit at position n to 1", category="bitwise")
    async def set_bit(self, a: int, n: int) -> Dict:
        return {"result": a | (1 << n), "operation": "set_bit", "a": a, "position": n}

    @tool(description="Clear bit at position n to 0", category="bitwise")
    async def clear_bit(self, a: int, n: int) -> Dict:
        return {"result": a & ~(1 << n), "operation": "clear_bit", "a": a, "position": n}

    @tool(description="Toggle bit at position n", category="bitwise")
    async def toggle_bit(self, a: int, n: int) -> Dict:
        return {"result": a ^ (1 << n), "operation": "toggle_bit", "a": a, "position": n}

    @tool(description="Count contiguous 1-bit blocks in binary representation", category="bitwise")
    async def bit_blocks(self, a: int) -> Dict:
        blocks = len(re.findall('1+', bin(a)[2:]))
        return {"result": blocks, "operation": "bit_blocks", "a": a}

    # ══════════════════════════════════════════════════════════════════════════
    # ADVANCED MATH (IDs 150-249)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Check if n is prime", category="math")
    async def is_prime(self, n: int) -> Dict:
        if n < 2: return {"result": False, "n": n}
        if n in (2, 3): return {"result": True, "n": n}
        if n % 2 == 0 or n % 3 == 0: return {"result": False, "n": n}
        i, w = 5, 2
        while i * i <= n:
            if n % i == 0: return {"result": False, "n": n}
            i += w; w = 6 - w
        return {"result": True, "n": n}

    @tool(description="Generate all primes up to n (Sieve of Eratosthenes)", category="math")
    async def primes_up_to(self, n: int) -> Dict:
        if n < 2: return {"result": [], "n": n, "count": 0}
        sieve = [True] * (n + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(n ** 0.5) + 1):
            if sieve[i]:
                for j in range(i*i, n+1, i):
                    sieve[j] = False
        primes = [i for i in range(2, n+1) if sieve[i]]
        return {"result": primes, "count": len(primes), "n": n}

    @tool(description="Prime factorization of n", category="math")
    async def prime_factors(self, n: int) -> Dict:
        d, factors = 2, []
        while d * d <= n:
            while n % d == 0:
                factors.append(d)
                n //= d
            d += 1
        if n > 1: factors.append(n)
        return {"result": factors, "input": n}

    @tool(description="Greatest common divisor (Euclidean algorithm)", category="math")
    async def gcd(self, a: int, b: int) -> Dict:
        a_orig, b_orig = a, b
        while b: a, b = b, a % b
        return {"result": abs(a), "a": a_orig, "b": b_orig, "operation": "gcd"}

    @tool(description="Least common multiple", category="math")
    async def lcm(self, a: int, b: int) -> Dict:
        return {"result": abs(a * b) // math.gcd(a, b) if a and b else 0, "a": a, "b": b, "operation": "lcm"}

    @tool(description="Extended GCD: returns (g, x, y) where ax + by = g", category="math")
    async def extended_gcd(self, a: int, b: int) -> Dict:
        if b == 0: return {"g": abs(a), "x": 1 if a > 0 else -1, "y": 0, "a": a, "b": b}
        x0, x1, y0, y1 = 1, 0, 0, 1
        while b:
            q = a // b
            a, b = b, a - q * b
            x0, x1 = x1, x0 - q * x1
            y0, y1 = y1, y0 - q * y1
        return {"g": abs(a), "x": x0, "y": y0, "a": a, "b": b}

    @tool(description="Fibonacci number (O(1) Binet formula with correction)", category="math")
    async def fibonacci(self, n: int) -> Dict:
        if n < 0: return {"result": None, "error": "n must be non-negative"}
        if n <= 1: return {"result": n, "n": n}
        phi = (1 + math.sqrt(5)) / 2
        val = round(phi ** n / math.sqrt(5))
        return {"result": val, "n": n, "method": "binet"}

    @tool(description="Factorial n! (iterative, large-int safe)", category="math")
    async def factorial(self, n: int) -> Dict:
        if n < 0: return {"result": None, "error": "n must be non-negative"}
        r = 1
        for i in range(2, n+1): r *= i
        return {"result": r, "n": n}

    @tool(description="Combinations C(n, r) = n! / (r!(n-r)!)", category="math")
    async def combinations(self, n: int, r: int) -> Dict:
        if r < 0 or r > n: return {"result": 0, "n": n, "r": r}
        r = min(r, n - r)
        result = 1
        for i in range(1, r+1):
            result = result * (n - r + i) // i
        return {"result": result, "n": n, "r": r}

    @tool(description="Permutations P(n, r) = n! / (n-r)!", category="math")
    async def permutations(self, n: int, r: int) -> Dict:
        if r < 0 or r > n: return {"result": 0, "n": n, "r": r}
        result = 1
        for i in range(n, n-r, -1): result *= i
        return {"result": result, "n": n, "r": r}

    @tool(description="Binomial coefficient C(n, k)", category="math")
    async def binomial_coeff(self, n: int, k: int) -> Dict:
        return self.combinations(n, k)

    @tool(description="Combinations with repetition C'(n, r) = C(n+r-1, r)", category="math")
    async def combinations_with_repetition(self, n: int, r: int) -> Dict:
        return self.combinations(n + r - 1, r)

    @tool(description="Permutations with repetition P'(n, r) = n^r", category="math")
    async def permutations_with_repetition(self, n: int, r: int) -> Dict:
        return {"result": n ** r, "n": n, "r": r}

    @tool(description="Hypotenuse: sqrt(a^2 + b^2)", category="math")
    async def hypot(self, a: float, b: float) -> Dict:
        return {"result": math.hypot(a, b), "a": a, "b": b}

    @tool(description="Arc tangent 2: atan2(y, x) giving correct quadrant", category="math")
    async def atan2(self, y: float, x: float) -> Dict:
        return {"result": math.atan2(y, x), "y": y, "x": x, "radians": math.atan2(y, x)}

    @tool(description="Hyperbolic sine", category="math")
    async def sinh(self, x: float) -> Dict:
        return {"result": math.sinh(x), "x": x}

    @tool(description="Hyperbolic cosine", category="math")
    async def cosh(self, x: float) -> Dict:
        return {"result": math.cosh(x), "x": x}

    @tool(description="Hyperbolic tangent", category="math")
    async def tanh(self, x: float) -> Dict:
        return {"result": math.tanh(x), "x": x}

    @tool(description="Inverse hyperbolic sine", category="math")
    async def asinh(self, x: float) -> Dict:
        return {"result": math.asinh(x), "x": x}

    @tool(description="Inverse hyperbolic cosine", category="math")
    async def acosh(self, x: float) -> Dict:
        return {"result": math.acosh(x), "x": x}

    @tool(description="Inverse hyperbolic tangent", category="math")
    async def atanh(self, x: float) -> Dict:
        return {"result": math.atanh(x), "x": x}

    @tool(description="Logarithm of x in arbitrary base", category="math")
    async def log_base(self, x: float, base: float) -> Dict:
        if x <= 0 or base <= 0 or base == 1: return {"result": None, "error": "invalid args"}
        return {"result": math.log(x) / math.log(base), "x": x, "base": base}

    @tool(description="exp(x) - 1, accurate for small x", category="math")
    async def expm1(self, x: float) -> Dict:
        return {"result": math.expm1(x), "x": x}

    @tool(description="log(1 + x), accurate for small x", category="math")
    async def log1p(self, x: float) -> Dict:
        return {"result": math.log1p(x), "x": x}

    @tool(description="Sigmoid activation: 1 / (1 + exp(-x))", category="math")
    async def sigmoid(self, x: float) -> Dict:
        return {"result": 1 / (1 + math.exp(-x)), "x": x}

    @tool(description="Softplus: log(1 + exp(x))", category="math")
    async def softplus(self, x: float) -> Dict:
        return {"result": math.log(1 + math.exp(x)), "x": x}

    @tool(description="Exponential Linear Unit activation", category="math")
    async def elu(self, x: float, alpha: float = 1.0) -> Dict:
        return {"result": x if x >= 0 else alpha * (math.exp(x) - 1), "x": x, "alpha": alpha}

    @tool(description="Clamp value between lo and hi", category="math")
    async def clamp(self, v: float, lo: float, hi: float) -> Dict:
        return {"result": max(lo, min(hi, v)), "v": v, "lo": lo, "hi": hi}

    @tool(description="Fractional part of x", category="math")
    async def fract(self, x: float) -> Dict:
        return {"result": x - math.floor(x), "x": x}

    @tool(description="Truncate toward zero", category="math")
    async def trunc(self, x: float) -> Dict:
        return {"result": math.trunc(x), "x": x}

    @tool(description="Round to nearest integer", category="math")
    async def nearbyint(self, x: float) -> Dict:
        return {"result": math.nearbyint(x), "x": x}

    @tool(description="Degrees to radians", category="math")
    async def degrees_to_radians(self, d: float) -> Dict:
        return {"result": math.radians(d), "degrees": d}

    @tool(description="Radians to degrees", category="math")
    async def radians_to_degrees(self, r: float) -> Dict:
        return {"result": math.degrees(r), "radians": r}

    @tool(description="Sign of x (-1, 0, or 1)", category="math")
    async def sign(self, x: float) -> Dict:
        return {"result": (1 if x > 0 else -1 if x < 0 else 0), "x": x}

    # ══════════════════════════════════════════════════════════════════════════
    # STATISTICS (IDs 250-299)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Mean absolute deviation", category="statistics")
    async def mean_abs_dev(self, values: List[float]) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        m = sum(values) / len(values)
        return {"result": sum(abs(v - m) for v in values) / len(values), "mean": m}

    @tool(description="Root mean square", category="statistics")
    async def rms(self, values: List[float]) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        return {"result": math.sqrt(sum(v*v for v in values) / len(values))}

    @tool(description="Population variance", category="statistics")
    async def variance(self, values: List[float]) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        m = sum(values) / len(values)
        return {"result": sum((v - m)**2 for v in values) / len(values)}

    @tool(description="Population standard deviation", category="statistics")
    async def stdev(self, values: List[float]) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        m = sum(values) / len(values)
        var = sum((v - m)**2 for v in values) / len(values)
        return {"result": math.sqrt(var)}

    @tool(description="Median value", category="statistics")
    async def median(self, values: List[float]) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        s = sorted(values)
        n = len(s)
        mid = s[n//2]
        return {"result": mid if n % 2 == 1 else (s[n//2 - 1] + s[n//2]) / 2}

    @tool(description="Mode (most frequent value)", category="statistics")
    async def mode(self, values: List[float]) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        freq = {}
        for v in values:
            freq[v] = freq.get(v, 0) + 1
        mode_val = max(freq, key=freq.get)
        return {"result": mode_val, "count": freq[mode_val]}

    @tool(description="Percentile value (p must be 0-100)", category="statistics")
    async def percentile(self, values: List[float], p: float) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        s = sorted(values)
        k = (len(s) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c: return {"result": s[int(k)]}
        d0 = s[int(f)] * (c - k)
        d1 = s[int(c)] * (k - f)
        return {"result": d0 + d1, "p": p}

    @tool(description="Pearson correlation coefficient", category="statistics")
    async def pearson_corr(self, x: List[float], y: List[float]) -> Dict:
        if len(x) != len(y) or len(x) < 2: return {"result": None, "error": "length mismatch or too few points"}
        n = len(x)
        mx, my = sum(x)/n, sum(y)/n
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        den = math.sqrt(sum((xi - mx)**2 for xi in x) * sum((yi - my)**2 for yi in y))
        return {"result": num / den if den else 0, "n": n}

    @tool(description="Spearman rank correlation (simplified)", category="statistics")
    async def spearman_corr(self, x: List[float], y: List[float]) -> Dict:
        if len(x) != len(y) or len(x) < 2: return {"result": None, "error": "length mismatch"}
        rx = sorted(enumerate(x), key=lambda p: p[1])
        ry = sorted(enumerate(y), key=lambda p: p[1])
        rank_x = [0] * len(x)
        rank_y = [0] * len(y)
        for i, (idx, _) in enumerate(rx): rank_x[idx] = i + 1
        for i, (idx, _) in enumerate(ry): rank_y[idx] = i + 1
        d2 = sum((rx[i][0] - ry[i][0])**2 for i in range(len(x)))
        n = len(x)
        return {"result": 1 - (6 * d2) / (n * (n**2 - 1))}

    @tool(description="Z-score normalization", category="statistics")
    async def z_score(self, value: float, mean: float, stdev: float) -> Dict:
        return {"result": (value - mean) / stdev if stdev else 0, "value": value, "mean": mean, "stdev": stdev}

    @tool(description="Min-max normalization to [0,1]", category="statistics")
    async def normalize(self, values: List[float]) -> Dict:
        if not values: return {"result": [], "error": "empty list"}
        mn, mx = min(values), max(values)
        rng = mx - mn
        if rng == 0: return {"result": [0.5] * len(values)}
        return {"result": [(v - mn) / rng for v in values], "min": mn, "max": mx}

    @tool(description="Histogram bin counts", category="statistics")
    async def histogram(self, values: List[float], bins: int = 10) -> Dict:
        if not values: return {"result": [], "error": "empty list"}
        mn, mx = min(values), max(values)
        rng = mx - mn
        if rng == 0: return {"result": [len(values)], "bins": bins}
        bin_width = rng / bins
        counts = [0] * bins
        for v in values:
            idx = min(int((v - mn) / bin_width), bins - 1)
            counts[idx] += 1
        return {"counts": counts, "bin_width": bin_width, "min": mn, "max": mx}

    @tool(description="Exponentially weighted moving average", category="statistics")
    async def ewma(self, values: List[float], alpha: float = 0.3) -> Dict:
        if not values: return {"result": None, "error": "empty list"}
        result = [values[0]]
        for v in values[1:]:
            result.append(alpha * v + (1 - alpha) * result[-1])
        return {"result": result, "alpha": alpha}

    @tool(description="Moving average", category="statistics")
    async def moving_average(self, values: List[float], window: int = 3) -> Dict:
        if len(values) < window: return {"result": [], "error": "window too large"}
        result = []
        for i in range(len(values) - window + 1):
            result.append(sum(values[i:i+window]) / window)
        return {"result": result, "window": window}

    @tool(description="Shannon entropy in bits", category="statistics")
    async def entropy(self, values: List[float]) -> Dict:
        if not values: return {"result": 0}
        total = sum(values)
        if total == 0: return {"result": 0}
        probs = [v / total for v in values if v > 0]
        return {"result": -sum(p * math.log2(p) for p in probs)}

    # ══════════════════════════════════════════════════════════════════════════
    # SEQUENCES (IDs 300-349)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Generate arithmetic sequence", category="sequences")
    async def arithmetic_seq(self, start: float, diff: float, n: int) -> Dict:
        return {"result": [start + i * diff for i in range(n)], "start": start, "diff": diff, "n": n}

    @tool(description="Generate geometric sequence", category="sequences")
    async def geometric_seq(self, start: float, ratio: float, n: int) -> Dict:
        return {"result": [start * (ratio ** i) for i in range(n)], "start": start, "ratio": ratio, "n": n}

    @tool(description="Check if string is palindrome", category="sequences")
    async def is_palindrome(self, s: str) -> Dict:
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
        return {"result": cleaned == cleaned[::-1], "string": s}

    @tool(description="Longest palindromic substring (O(n^2) dynamic approach)", category="sequences")
    async def longest_palindromic_substring(self, s: str) -> Dict:
        if not s: return {"result": "", "string": s}
        best, best_len = "", 0
        n = len(s)
        dp = [[False] * n for _ in range(n)]
        for i in range(n):
            dp[i][i] = True
            best, best_len = s[i], 1
        for length in range(2, n + 1):
            for i in range(n - length + 1):
                j = i + length - 1
                if length == 2:
                    ok = s[i] == s[j]
                else:
                    ok = s[i] == s[j] and dp[i+1][j-1]
                if ok:
                    dp[i][j] = True
                    if length > best_len:
                        best, best_len = s[i:j+1], length
        return {"result": best, "length": best_len, "string": s}

    @tool(description="Collatz sequence from n until reaching 1", category="sequences")
    async def collatz_sequence(self, n: int) -> Dict:
        seq = [n]
        while n != 1:
            n = n // 2 if n % 2 == 0 else 3 * n + 1
            seq.append(n)
        return {"result": seq, "steps": len(seq) - 1}

    @tool(description="Collatz steps count to reach 1", category="sequences")
    async def collatz_steps(self, n: int) -> Dict:
        steps = 0
        while n != 1:
            n = n // 2 if n % 2 == 0 else 3 * n + 1
            steps += 1
        return {"result": steps, "start": n}

    @tool(description="Josephus problem survivor (n people, skip k)", category="sequences")
    async def josephus(self, n: int, k: int) -> Dict:
        if n < 1: return {"result": 0}
        survivor = 0
        for i in range(2, n + 1):
            survivor = (survivor + k) % i
        return {"result": survivor + 1, "n": n, "k": k}

    @tool(description="Binary search in sorted list", category="sequences")
    async def binary_search(self, sorted_list: List[float], target: float) -> Dict:
        lo, hi = 0, len(sorted_list) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if sorted_list[mid] == target:
                return {"result": mid, "index": mid, "found": True}
            elif sorted_list[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        return {"result": None, "index": -1, "found": False}

    # ══════════════════════════════════════════════════════════════════════════
    # MATRIX-LIKE 2x2 OPERATIONS (IDs 350-399)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="2x2 matrix multiply [[a,b],[c,d]] x [[e,f],[g,h]]", category="matrix")
    async def matrix_multiply_2x2(self, a: float, b: float, c: float, d: float,
                                   e: float, f: float, g: float, h: float) -> Dict:
        return {
            "result": [[a*e + b*g, a*f + b*h], [c*e + d*g, c*f + d*h]],
            "operation": "2x2_matrix_multiply"
        }

    @tool(description="2x2 determinant ad - bc", category="matrix")
    async def determinant_2x2(self, a: float, b: float, c: float, d: float) -> Dict:
        return {"result": a * d - b * c, "a": a, "b": b, "c": c, "d": d}

    @tool(description="3x3 determinant (rule of Sarrus)", category="matrix")
    async def determinant_3x3(self, m: List[List[float]]) -> Dict:
        if len(m) != 3 or any(len(r) != 3 for r in m): return {"error": "need 3x3 matrix"}
        a, b, c, d, e, f, g, h, i_ = m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2], m[2][0], m[2][1], m[2][2]
        det = (a*e*i_ + b*f*g + c*d*h) - (c*e*g + b*d*i_ + a*f*h)
        return {"result": det, "matrix": m}

    @tool(description="2D vector dot product", category="matrix")
    async def vector_dot(self, ax: float, ay: float, bx: float, by: float) -> Dict:
        return {"result": ax * bx + ay * by, "a": [ax, ay], "b": [bx, by]}

    @tool(description="2D vector cross product magnitude (ax*by - ay*bx)", category="matrix")
    async def vector_cross(self, ax: float, ay: float, bx: float, by: float) -> Dict:
        return {"result": ax * by - ay * bx, "a": [ax, ay], "b": [bx, by]}

    @tool(description="2D vector L2 norm", category="matrix")
    async def vector_norm(self, x: float, y: float) -> Dict:
        return {"result": math.sqrt(x*x + y*y), "vector": [x, y]}

    @tool(description="Normalize 2D vector to unit length", category="matrix")
    async def vector_normalize(self, x: float, y: float) -> Dict:
        n = math.sqrt(x*x + y*y)
        if n == 0: return {"result": [0.0, 0.0], "vector": [x, y]}
        return {"result": [x/n, y/n], "norm": n, "vector": [x, y]}

    @tool(description="Add two 2x2 matrices", category="matrix")
    async def matrix_add(self, a: float, b: float, c: float, d: float,
                          e: float, f: float, g: float, h: float) -> Dict:
        return {"result": [[a+e, b+f], [c+g, d+h]]}

    @tool(description="Scale 2x2 matrix by scalar", category="matrix")
    async def matrix_scale(self, a: float, b: float, c: float, d: float, s: float) -> Dict:
        return {"result": [[a*s, b*s], [c*s, d*s]], "scalar": s}

    @tool(description="2x2 identity matrix", category="matrix")
    async def identity_2x2(self) -> Dict:
        return {"result": [[1.0, 0.0], [0.0, 1.0]]}

    @tool(description="2x2 zero matrix", category="matrix")
    async def zero_2x2(self) -> Dict:
        return {"result": [[0.0, 0.0], [0.0, 0.0]]}

    @tool(description="Rotate 2D point by angle (radians) around origin", category="matrix")
    async def rotate_2d(self, x: float, y: float, angle: float) -> Dict:
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return {"result": [x * cos_a - y * sin_a, x * sin_a + y * cos_a], "angle_radians": angle}

    @tool(description="Scale 2D point by (sx, sy)", category="matrix")
    async def scale_2d(self, x: float, y: float, sx: float, sy: float) -> Dict:
        return {"result": [x * sx, y * sy], "sx": sx, "sy": sy}

    @tool(description="Translate 2D point by (tx, ty)", category="matrix")
    async def translate_2d(self, x: float, y: float, tx: float, ty: float) -> Dict:
        return {"result": [x + tx, y + ty], "tx": tx, "ty": ty}

    @tool(description="Solve 2x2 linear system via Cramer's rule", category="matrix")
    async def solve_linear_2x2(self, a: float, b: float, c: float, d: float,
                               e: float, f: float) -> Dict:
        det = a * d - b * c
        if det == 0: return {"result": None, "error": "singular system"}
        return {"result": [(d*e - b*f) / det, (a*f - c*e) / det], "det": det}

    # ══════════════════════════════════════════════════════════════════════════
    # COMPLEX & BIG INTEGER (IDs 400-449)
    # ══════════════════════════════════════════════════════════════════════════

    @tool(description="Complex number addition", category="complex")
    async def cadd(self, ar: float, ai: float, br: float, bi: float) -> Dict:
        return {"result": [ar + br, ai + bi], "a": [ar, ai], "b": [br, bi]}

    @tool(description="Complex number subtraction", category="complex")
    async def csub(self, ar: float, ai: float, br: float, bi: float) -> Dict:
        return {"result": [ar - br, ai - bi], "a": [ar, ai], "b": [br, bi]}

    @tool(description="Complex number multiplication", category="complex")
    async def cmul(self, ar: float, ai: float, br: float, bi: float) -> Dict:
        return {"result": [ar*br - ai*bi, ar*bi + ai*br], "a": [ar, ai], "b": [br, bi]}

    @tool(description="Complex number division", category="complex")
    async def cdiv(self, ar: float, ai: float, br: float, bi: float) -> Dict:
        denom = br*br + bi*bi
        if denom == 0: return {"error": "division by zero"}
        return {"result": [(ar*br + ai*bi) / denom, (ai*br - ar*bi) / denom], "a": [ar, ai], "b": [br, bi]}

    @tool(description="Complex magnitude |a + bi|", category="complex")
    async def complex_magnitude(self, r: float, i: float) -> Dict:
        return {"result": abs(complex(r, i)), "complex": [r, i]}

    @tool(description="Complex phase angle in radians", category="complex")
    async def complex_phase(self, r: float, i: float) -> Dict:
        return {"result": cmath.phase(complex(r, i)), "complex": [r, i]}

    @tool(description="Convert complex to polar form (r, theta)", category="complex")
    async def complex_polar(self, r: float, i: float) -> Dict:
        z = complex(r, i)
        return {"result": [abs(z), cmath.phase(z)], "complex": [r, i]}

    @tool(description="Big factorial using Python's arbitrary precision ints", category="math")
    async def factorial_big(self, n: int) -> Dict:
        if n < 0: return {"result": None, "error": "n must be non-negative"}
        r = 1
        for i in range(2, n + 1): r *= i
        return {"result": r, "digits": len(str(r)), "n": n}

    @tool(description="Big combinations using Python's arbitrary precision", category="math")
    async def combinations_big(self, n: int, r: int) -> Dict:
        if r < 0 or r > n: return {"result": 0}
        r = min(r, n - r)
        result = 1
        for i in range(1, r + 1):
            result = result * (n - r + i) // i
        return {"result": result, "n": n, "r": r}