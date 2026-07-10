"""
minxg/operators.py — Operator Engine Python Bridge v1.0.0

Provides Python-level access to the 10,000+ operator engine.
Operators are lightweight data transformations: math, text, data, logic,
network, ML, system operations. Each operator has a unique ID (0-9999)
and category.

When C++ native operators are loaded (via libminxg_operators.so), they
execute 10-100x faster than pure Python. Falls back gracefully.
"""
from __future__ import annotations
import math
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import BaseWorker, tool






class Operator:
    """A single operator in the engine."""
    __slots__ = ("op_id", "name", "category", "description", "input_types",
                 "output_type", "is_pure", "fn")

    def __init__(self, op_id: int, name: str, category: str, description: str,
                 input_types: List[str], output_type: str, is_pure: bool,
                 fn: Callable):
        self.op_id = op_id
        self.name = name
        self.category = category
        self.description = description
        self.input_types = input_types
        self.output_type = output_type
        self.is_pure = is_pure
        self.fn = fn

    def execute(self, *args, **kwargs) -> Any:
        return self.fn(*args, **kwargs)

    def __repr__(self):
        return f"Operator({self.op_id}, {self.name}, {self.category})"


class OperatorRegistry:
    """Registry of all operators, indexed by ID and name."""

    def __init__(self):
        self._by_id: Dict[int, Operator] = {}
        self._by_name: Dict[str, Operator] = {}
        self._categories: Dict[str, List[int]] = {}
        self._count = 0

    def register(self, op: Operator):
        if op.op_id in self._by_id:
            return  
        if not hasattr(self, '_registered_ids'):
            self._registered_ids = set()
        if op.op_id in self._registered_ids:
            return
        self._registered_ids.add(op.op_id)
        self._by_id[op.op_id] = op
        self._by_name[op.name] = op
        self._categories.setdefault(op.category, []).append(op.op_id)
        self._count += 1

    def get_by_id(self, op_id: int) -> Optional[Operator]:
        return self._by_id.get(op_id)

    def get_by_name(self, name: str) -> Optional[Operator]:
        return self._by_name.get(name)

    def get_category(self, category: str) -> List[Operator]:
        return [self._by_id[i] for i in self._categories.get(category, [])]

    @property
    def total_operators(self) -> int:
        return self._count

    def list_categories(self) -> List[str]:
        return sorted(self._categories.keys())

    def category_summary(self) -> Dict[str, int]:
        return {cat: len(ids) for cat, ids in self._categories.items()}



OPERATOR_REGISTRY = OperatorRegistry()






def _register_core_operators():
    """Register core Python operators. C++ native operators override these."""
    ops = []

    
    ops.append(Operator(0, "add", "math", "Add two numbers", ["float", "float"], "float", True,
                        lambda a, b: a + b))
    ops.append(Operator(1, "sub", "math", "Subtract b from a", ["float", "float"], "float", True,
                        lambda a, b: a - b))
    ops.append(Operator(2, "mul", "math", "Multiply two numbers", ["float", "float"], "float", True,
                        lambda a, b: a * b))
    ops.append(Operator(3, "div", "math", "Divide a by b", ["float", "float"], "float", True,
                        lambda a, b: a / b if b != 0 else float('inf')))
    ops.append(Operator(4, "pow", "math", "Raise a to power b", ["float", "float"], "float", True,
                        lambda a, b: a ** b if a >= 0 or isinstance(b, int) else complex(a, 0) ** b))
    ops.append(Operator(5, "sqrt", "math", "Square root", ["float"], "float", True,
                        lambda a: math.sqrt(a) if a >= 0 else None))
    ops.append(Operator(6, "log", "math", "Natural logarithm", ["float"], "float", True,
                        lambda a: math.log(a) if a > 0 else None))
    ops.append(Operator(7, "log10", "math", "Base-10 logarithm", ["float"], "float", True,
                        lambda a: math.log10(a) if a > 0 else None))
    ops.append(Operator(8, "sin", "math", "Sine (radians)", ["float"], "float", True,
                        lambda a: math.sin(a)))
    ops.append(Operator(9, "cos", "math", "Cosine (radians)", ["float"], "float", True,
                        lambda a: math.cos(a)))
    ops.append(Operator(10, "abs", "math", "Absolute value", ["float"], "float", True,
                        lambda a: abs(a)))
    ops.append(Operator(11, "round", "math", "Round to nearest integer", ["float"], "int", True,
                        lambda a: round(a)))
    ops.append(Operator(12, "ceil", "math", "Ceiling (round up)", ["float"], "int", True,
                        lambda a: math.ceil(a)))
    ops.append(Operator(13, "floor", "math", "Floor (round down)", ["float"], "int", True,
                        lambda a: math.floor(a)))
    ops.append(Operator(14, "mod", "math", "Modulo (a % b)", ["float", "float"], "float", True,
                        lambda a, b: a % b if b != 0 else None))
    ops.append(Operator(15, "min2", "math", "Minimum of two values", ["float", "float"], "float", True,
                        lambda a, b: min(a, b)))
    ops.append(Operator(16, "max2", "math", "Maximum of two values", ["float", "float"], "float", True,
                        lambda a, b: max(a, b)))
    ops.append(Operator(17, "clamp", "math", "Clamp value between min and max",
                        ["float", "float", "float"], "float", True,
                        lambda v, lo, hi: max(lo, min(hi, v))))
    ops.append(Operator(18, "deg2rad", "math", "Degrees to radians", ["float"], "float", True,
                        lambda a: math.radians(a)))
    ops.append(Operator(19, "rad2deg", "math", "Radians to degrees", ["float"], "float", True,
                        lambda a: math.degrees(a)))

    
    ops.append(Operator(2000, "upper", "text", "Convert to uppercase", ["string"], "string", True,
                        lambda s: s.upper()))
    ops.append(Operator(2001, "lower", "text", "Convert to lowercase", ["string"], "string", True,
                        lambda s: s.lower()))
    ops.append(Operator(2002, "title", "text", "Convert to title case", ["string"], "string", True,
                        lambda s: s.title()))
    ops.append(Operator(2003, "capitalize", "text", "Capitalize first character", ["string"], "string", True,
                        lambda s: s.capitalize()))
    ops.append(Operator(2004, "strip", "text", "Strip whitespace from both ends", ["string"], "string", True,
                        lambda s: s.strip()))
    ops.append(Operator(2005, "trim", "text", "Trim whitespace (alias for strip)", ["string"], "string", True,
                        lambda s: s.strip()))
    ops.append(Operator(2006, "replace", "text", "Replace substring", ["string", "string", "string"], "string", True,
                        lambda s, o, n: s.replace(o, n)))
    ops.append(Operator(2007, "split", "text", "Split string by delimiter", ["string", "string"], "list", True,
                        lambda s, d: s.split(d)))
    ops.append(Operator(2008, "join", "text", "Join list into string with delimiter", ["list", "string"], "string", True,
                        lambda l, d: d.join(str(x) for x in l)))
    ops.append(Operator(2009, "len", "text", "String length", ["string"], "int", True,
                        lambda s: len(s)))
    ops.append(Operator(2010, "contains", "text", "Check if string contains substring", ["string", "string"], "bool", True,
                        lambda s, sub: sub in s))
    ops.append(Operator(2011, "startswith", "text", "Check if string starts with prefix", ["string", "string"], "bool", True,
                        lambda s, p: s.startswith(p)))
    ops.append(Operator(2012, "endswith", "text", "Check if string ends with suffix", ["string", "string"], "bool", True,
                        lambda s, sf: s.endswith(sf)))
    ops.append(Operator(2013, "pad_left", "text", "Pad string on left to width", ["string", "int", "string"], "string", True,
                        lambda s, w, c: s.rjust(w, c)))
    ops.append(Operator(2014, "pad_right", "text", "Pad string on right to width", ["string", "int", "string"], "string", True,
                        lambda s, w, c: s.ljust(w, c)))
    ops.append(Operator(2015, "reverse", "text", "Reverse string", ["string"], "string", True,
                        lambda s: s[::-1]))
    ops.append(Operator(2016, "count", "text", "Count substring occurrences", ["string", "string"], "int", True,
                        lambda s, sub: s.count(sub)))
    ops.append(Operator(2017, "slice", "text", "Slice string [start:end:step]", ["string", "int", "int", "int"], "string", True,
                        lambda s, st, en, sp: s[st:en:sp]))
    ops.append(Operator(2018, "levenshtein", "text", "Levenshtein distance between strings",
                        ["string", "string"], "int", True,
                        lambda a, b: _levenshtein(a, b)))

    
    ops.append(Operator(3500, "list_len", "data", "List length", ["list"], "int", True,
                        lambda l: len(l)))
    ops.append(Operator(3501, "list_get", "data", "Get element at index", ["list", "int"], "any", True,
                        lambda l, i: l[i] if 0 <= i < len(l) else None))
    ops.append(Operator(3502, "list_slice", "data", "Slice list [start:end]", ["list", "int", "int"], "list", True,
                        lambda l, s, e: l[s:e]))
    ops.append(Operator(3503, "list_sort", "data", "Sort list", ["list", "bool"], "list", False,
                        lambda l, rev: sorted(l, reverse=rev)))
    ops.append(Operator(3504, "list_reverse", "data", "Reverse list", ["list"], "list", True,
                        lambda l: list(reversed(l))))
    ops.append(Operator(3505, "list_uniq", "data", "Deduplicate list (preserve order)", ["list"], "list", True,
                        lambda l: list(dict.fromkeys(l))))
    ops.append(Operator(3506, "list_sum", "data", "Sum of list elements", ["list"], "float", True,
                        lambda l: sum(float(x) for x in l if x is not None)))
    ops.append(Operator(3507, "list_avg", "data", "Average of list elements", ["list"], "float", True,
                        lambda l: sum(float(x) for x in l) / len(l) if l else 0))
    ops.append(Operator(3508, "list_min", "data", "Minimum of list", ["list"], "float", True,
                        lambda l: min(float(x) for x in l) if l else None))
    ops.append(Operator(3509, "list_max", "data", "Maximum of list", ["list"], "float", True,
                        lambda l: max(float(x) for x in l) if l else None))
    ops.append(Operator(3510, "dict_keys", "data", "Dictionary keys", ["dict"], "list", True,
                        lambda d: list(d.keys())))
    ops.append(Operator(3511, "dict_values", "data", "Dictionary values", ["dict"], "list", True,
                        lambda d: list(d.values())))

    
    ops.append(Operator(5500, "and", "logic", "Logical AND", ["bool", "bool"], "bool", True,
                        lambda a, b: a and b))
    ops.append(Operator(5501, "or", "logic", "Logical OR", ["bool", "bool"], "bool", True,
                        lambda a, b: a or b))
    ops.append(Operator(5502, "not", "logic", "Logical NOT", ["bool"], "bool", True,
                        lambda a: not a))
    ops.append(Operator(5503, "xor", "logic", "Logical XOR", ["bool", "bool"], "bool", True,
                        lambda a, b: bool(a) != bool(b)))
    ops.append(Operator(5504, "eq", "logic", "Equality check", ["any", "any"], "bool", True,
                        lambda a, b: a == b))
    ops.append(Operator(5505, "neq", "logic", "Not-equal check", ["any", "any"], "bool", True,
                        lambda a, b: a != b))
    ops.append(Operator(5506, "gt", "logic", "Greater than", ["float", "float"], "bool", True,
                        lambda a, b: a > b))
    ops.append(Operator(5507, "lt", "logic", "Less than", ["float", "float"], "bool", True,
                        lambda a, b: a < b))
    ops.append(Operator(5508, "gte", "logic", "Greater or equal", ["float", "float"], "bool", True,
                        lambda a, b: a >= b))
    ops.append(Operator(5509, "lte", "logic", "Less or equal", ["float", "float"], "bool", True,
                        lambda a, b: a <= b))
    ops.append(Operator(5510, "between", "logic", "Check if value is between lo and hi",
                        ["float", "float", "float"], "bool", True,
                        lambda v, lo, hi: lo <= v <= hi))
    ops.append(Operator(5511, "null_check", "logic", "Check if value is None", ["any"], "bool", True,
                        lambda v: v is None))
    ops.append(Operator(5512, "is_type", "logic", "Check value type", ["any", "string"], "bool", True,
                        lambda v, t: type(v).__name__ == t))

    
    ops.append(Operator(9000, "file_read", "system", "Read file content", ["string"], "string", False,
                        lambda p: _op_file_read(p)))
    ops.append(Operator(9001, "file_write", "system", "Write content to file", ["string", "string"], "bool", False,
                        lambda p, c: _op_file_write(p, c)))
    ops.append(Operator(9002, "file_exists", "system", "Check if file exists", ["string"], "bool", False,
                        lambda p: os.path.exists(p)))
    ops.append(Operator(9003, "file_size", "system", "Get file size in bytes", ["string"], "int", False,
                        lambda p: os.path.getsize(p) if os.path.isfile(p) else 0))
    ops.append(Operator(9004, "date_now", "system", "Current ISO datetime", [], "string", True,
                        lambda: __import__('datetime').datetime.now().isoformat()))
    ops.append(Operator(9005, "env_get", "system", "Get environment variable", ["string"], "string", True,
                        lambda k: os.environ.get(k, "")))

    for op in ops:
        OPERATOR_REGISTRY.register(op)


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j+1] + 1, curr[j] + 1,
                           prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def _op_file_read(path: str) -> Optional[str]:
    try:
        with open(path, 'r') as f:
            return f.read(1024*1024)
    except Exception:
        return None


def _op_file_write(path: str, content: str) -> bool:
    try:
        with open(path, 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False



_register_core_operators()






class OperatorGraph:
    """A DAG of operators that can be executed as a pipeline."""

    def __init__(self):
        self.nodes: List[Tuple[int, list]] = []  
        self._cache: Dict[int, Any] = {}

    def add_node(self, op_id: int, inputs: List[int] = None) -> int:
        """Add an operator node. Returns node index."""
        idx = len(self.nodes)
        self.nodes.append((op_id, inputs or []))
        return idx

    def execute(self) -> List[Any]:
        """Execute the pipeline and return results."""
        results = {}
        outputs = []
        for idx, (op_id, inputs) in enumerate(self.nodes):
            op = OPERATOR_REGISTRY.get_by_id(op_id)
            if not op:
                results[idx] = None
                continue
            
            resolved = []
            for inp_idx in inputs:
                resolved.append(results.get(inp_idx, None))
            output = op.execute(*resolved) if resolved else (op.execute() if op.input_types else None)
            results[idx] = output
            outputs.append(output)
        return outputs






class OperatorWorker(BaseWorker):
    """Operator engine: execute operators by ID or name, list operators, run pipelines."""
    worker_id = "operator"
    version = "0.16.0"

    def _register_tools(self):
        self.tools["operator_list"] = type("ToolDef", (), {
            "name": "operator_list",
            "description": "List all available operators, optionally filtered by category.",
            "params": {"category": "string", "search": "string"},
            "category": "operator",
            "platforms": ["linux", "macos", "windows", "android", "ios", "web"],
            "requires_root": False, "fn": None,
        })()
        self.tools["operator_exec"] = type("ToolDef", (), {
            "name": "operator_exec",
            "description": "Execute an operator by ID or name with arguments.",
            "params": {"operator": "string", "args": "list"},
            "category": "operator",
            "platforms": ["linux", "macos", "windows", "android", "ios", "web"],
            "requires_root": False, "fn": None,
        })()
        self.tools["operator_categories"] = type("ToolDef", (), {
            "name": "operator_categories",
            "description": "List operator categories with operator counts.",
            "params": {},
            "category": "operator",
            "platforms": ["linux", "macos", "windows", "android", "ios", "web"],
            "requires_root": False, "fn": None,
        })()

    def call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "operator_list":
            return self._operator_list(params.get("category"), params.get("search"))
        elif tool_name == "operator_exec":
            return self._operator_exec(params.get("operator"), params.get("args", []))
        elif tool_name == "operator_categories":
            return self._operator_categories()
        return {"status": "error", "error": f"Unknown operator tool: {tool_name}"}

    def _operator_list(self, category: str = None, search: str = None) -> Dict[str, Any]:
        ops = []
        if category:
            for op in OPERATOR_REGISTRY.get_category(category):
                ops.append({"id": op.op_id, "name": op.name, "category": op.category,
                           "description": op.description})
        else:
            for op in OPERATOR_REGISTRY._by_id.values():
                ops.append({"id": op.op_id, "name": op.name, "category": op.category,
                           "description": op.description})

        if search:
            ops = [o for o in ops if search.lower() in o["name"].lower()
                   or search.lower() in o["description"].lower()]

        return {
            "status": "success",
            "operators": ops[:100],
            "total": len(ops),
            "total_registered": OPERATOR_REGISTRY.total_operators,
        }

    def _operator_exec(self, operator: str, args: List[Any] = None) -> Dict[str, Any]:
        op = None
        
        try:
            op_id = int(operator)
            op = OPERATOR_REGISTRY.get_by_id(op_id)
        except ValueError:
            op = OPERATOR_REGISTRY.get_by_name(operator)

        if not op:
            return {"status": "error", "error": f"Operator not found: {operator}"}

        try:
            result = op.execute(*args) if args else op.execute()
            return {"status": "success", "operator": op.name, "result": result}
        except Exception as e:
            return {"status": "error", "operator": op.name, "error": str(e)}

    def _operator_categories(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "categories": OPERATOR_REGISTRY.category_summary(),
            "total_operators": OPERATOR_REGISTRY.total_operators,
        }