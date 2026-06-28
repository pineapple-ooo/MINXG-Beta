"""Twin configuration and result types."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


class UnsupportedTwinOp(RuntimeError):
    def __init__(self, op_name: str, hint: str = "") -> None:
        super().__init__(f"unsupported op: {op_name} ({hint})")
        self.op_name = op_name
        self.hint = hint


@dataclass
class TwinConfig:
    # Empty string means "preserve the Python source's function name".
    # That's the saner default — a twin that emits an unnamed function
    # forces every caller to wrap and rename it, which is the opposite
    # of what ``python_to_rust`` is for. Override with a non-empty
    # literal when you want a stable exported name.
    function_name: str = ""
    target_language: str = "rust"
    use_i64_for_int: bool = True
    indent_size: int = 4


@dataclass
class TwinResult:
    source: str
    dependencies: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
