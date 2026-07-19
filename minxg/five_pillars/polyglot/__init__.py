"""Polyglot workers for MINXG — bridges to non-Python language runtimes.

Each worker exposes a small set of ``@tool``-decorated async methods that
forward to ``minxg.contracts.runtime.<lang>.invoke()``. When the runtime
is missing the tool returns ``{"status":"disabled","hint":...}`` rather
than raising, so the AI layer can surface failure cleanly.
"""

from .julia_worker import JuliaWorker
from .r_worker import RWorker
from .datalog_worker import DatalogWorker
from .wasm_worker import WasmWorker

__all__ = [
    "JuliaWorker",
    "RWorker",
    "DatalogWorker",
    "WasmWorker",
]