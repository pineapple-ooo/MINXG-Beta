"""minxg.twin — Python to Rust AST twin compiler.

The goal: take a Python function's AST and emit Cargo-compatible Rust
source code semantically equivalent to the function. The emit pattern
uses the OperatorGraph from minxg.polyglot so that:

    * Imports map to dependencies automatically.
    * Each Python statement becomes a Rust statement with explicit types.
    * The driver engine can run the same logic natively if compiled.

This is not a full Python compiler. It is a twin — the set of Python
constructs covered is enumerated below; anything outside falls through
to UnsupportedTwinOp which the caller can inspect.
"""
from .mapper import TwinConfig, TwinResult, UnsupportedTwinOp
from .python_to_rust import python_to_rust
from .rust_to_python import rust_to_python

__all__ = [
    "TwinConfig", "TwinResult", "UnsupportedTwinOp",
    "python_to_rust", "rust_to_python",
]
