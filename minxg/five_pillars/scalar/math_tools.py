"""
minxg/math_tools.py — Math & statistics tools.
Performance-critical base conversion delegated to C via core_native.
"""
from __future__ import annotations
import ast
import math
import random
import operator
from typing import Dict, List
from minxg.base import BaseWorker, tool

_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
}

_has_native = False
_base_convert = None

try:
    from .core_native import base_convert as _base_convert
    _has_native = True
except (ImportError, OSError):
    pass


def _safe_eval(node):
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        allowed = {"abs": abs, "round": round, "max": max, "min": min,
                   "sum": sum, "len": len}
        if isinstance(node.func, ast.Name) and node.func.id in allowed:
            args = [_safe_eval(a) for a in node.args]
            return allowed[node.func.id](*args)
    raise ValueError("unsupported expression")


class MathToolsWorker(BaseWorker):
    worker_id = "math_tools"
    version = "1.1.0"

    @tool(description="Safe math expression evaluation", category="calc")
    async def evaluate(self, expression: str) -> Dict:
        try:
            node = ast.parse(expression, mode="eval").body
            result = _safe_eval(node)
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"error": str(e), "expression": expression}

    @tool(description="Calculate mean, std, median, min/max", category="stats")
    async def mean_std(self, values: list) -> Dict:
        try:
            n = len(values)
            if n == 0:
                return {"error": "empty list"}
            mean = sum(values) / n
            variance = sum((x - mean) ** 2 for x in values) / n
            std = math.sqrt(variance)
            sorted_vals = sorted(values)
            median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
            return {"count": n, "mean": mean, "std": std, "median": median,
                    "min": min(values), "max": max(values), "sum": sum(values)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Generate random float in range", category="random")
    async def random_float(self, min_val: float = 0.0, max_val: float = 1.0) -> Dict:
        return {"value": random.uniform(min_val, max_val), "min": min_val, "max": max_val}

    @tool(description="Generate random integer in range", category="random")
    async def random_int(self, min_val: int = 0, max_val: int = 100) -> Dict:
        return {"value": random.randint(min_val, max_val), "min": min_val, "max": max_val}

    @tool(description="Base conversion (2-36) — C-native", category="convert")
    async def convert_base(self, number: str, from_base: int = 10, to_base: int = 16) -> Dict:
        if _has_native:
            try:
                result = _base_convert(number, from_base, to_base)
                return {"result": result, "from_base": from_base, "to_base": to_base}
            except Exception:
                pass
        try:
            if from_base == 10:
                n = int(number)
            else:
                n = int(number, from_base)
            if to_base == 10:
                result = str(n)
            elif to_base == 2:
                result = bin(n)[2:]
            elif to_base == 8:
                result = oct(n)[2:]
            elif to_base == 16:
                result = hex(n)[2:]
            else:
                digits = "0123456789abcdefghijklmnopqrstuvwxyz"
                if n == 0:
                    result = "0"
                else:
                    res = []
                    while n:
                        res.append(digits[n % to_base])
                        n //= to_base
                    result = "".join(reversed(res))
            return {"result": result, "from_base": from_base, "to_base": to_base}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Unit conversion", category="convert")
    async def convert_unit(self, value: float, from_unit: str, to_unit: str) -> Dict:
        try:
            result = _do_convert(value, from_unit.lower(), to_unit.lower())
            return {"value": value, "from": from_unit, "to": to_unit, "result": result}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Factorial n!", category="calc")
    async def factorial(self, n: int) -> Dict:
        try:
            return {"n": n, "result": math.factorial(n)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Permutation P(n,r)", category="calc")
    async def permutations(self, n: int, r: int) -> Dict:
        try:
            if r > n:
                return {"error": "r > n"}
            return {"n": n, "r": r, "result": math.perm(n, r)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Combination C(n,r)", category="calc")
    async def combinations(self, n: int, r: int) -> Dict:
        try:
            if r > n:
                return {"error": "r > n"}
            return {"n": n, "r": r, "result": math.comb(n, r)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Clamp value to [min_val, max_val] range", category="calc")
    async def clamp(self, value: float, min_val: float, max_val: float) -> Dict:
        result = max(min_val, min(max_val, value))
        return {"value": value, "min": min_val, "max": max_val, "result": result}


def _do_convert(value, fu, tu):
    length_to_m = {"km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
                   "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254}
    if fu in length_to_m and tu in length_to_m:
        return value * length_to_m[fu] / length_to_m[tu]
    weight_to_g = {"kg": 1000, "g": 1, "mg": 0.001, "lb": 453.59237, "oz": 28.3495}
    if fu in weight_to_g and tu in weight_to_g:
        return value * weight_to_g[fu] / weight_to_g[tu]
    if fu == "c":
        if tu == "f":
            return value * 9 / 5 + 32
        if tu == "k":
            return value + 273.15
    if fu == "f":
        if tu == "c":
            return (value - 32) * 5 / 9
        if tu == "k":
            return (value - 32) * 5 / 9 + 273.15
    if fu == "k":
        if tu == "c":
            return value - 273.15
        if tu == "f":
            return (value - 273.15) * 9 / 5 + 32
    raise ValueError(f"unsupported unit conversion: {fu} -> {tu}")