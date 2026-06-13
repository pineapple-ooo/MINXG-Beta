"""minxg.contracts — Operator Cell Architecture.

A pluggable contract framework. Every worker/ob●server in MINXG is a Cell that
implements a small interface and is discovered through a central Registry.
Cells know nothing about each other; interaction happens only through the
registry or through injected adapters.

Why this matters:

* Editing one Cell's implementation NEVER forces changes elsewhere.
* New Cells are added by registering — no central dispatch table to modify.
* The Registry handles capability queries, lifecycle, and dependency
  resolution without bloating individual Cells.

Three building blocks:

    Cell          – minimal capability unit (Protocol)
    Registry      – type-keyed provider catalogue (frozen after lock())
    Port          – asynchronous boundary used by Cells and external code
""""
from .cell import Cell, CellMeta, capability, requires
from .port import Port, Request, Response, PortError, port
from .registry import Registry, get_registry, reset_registry, cell
from .lifecycle import Lifecycle, LifecyclePhase

__all__ = [
    "Cell", "CellMeta", "capability", "requires",
    "Port", "Request", "Response", "PortError", "port",
    "Registry", "get_registry", "reset_registry", "cell",
    "Lifecycle", "LifecyclePhase",
]
