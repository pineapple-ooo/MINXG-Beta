"""minxg.polyglot — Multi-language AST normaliser.

Parses Python/Rust/JavaScript/Go/Shellscript into a single
`OperatorGraph` representation that the driver engine, evolution loop,
and contracts registry can all consume. The normalised form is the
mathematical graph `nodes = operators`, `edges = data flow`.

This is genuinely useful as a glue layer for migration: you can lift
an existing JS function into the driver, run drift tests, and emit
Python or Rust source from the canonical graph.
"""
from .graph import OperatorGraph, OperatorNode, OperatorEdge
from .normalizer import normalize
from .languages import detect_language, detect_language_from_path

__all__ = [
    "OperatorGraph", "OperatorNode", "OperatorEdge",
    "normalize", "detect_language", "detect_language_from_path",
]
