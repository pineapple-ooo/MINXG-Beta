"""minxg.self_evolution — Closed-loop self-improvement.

The driver engine is the *brain*, and `self_evolution` is the *immune
system*. Each cycle:

  1. FailureTour collects failed executions from driver step reports.
  2. FieldForge inspects the failures and proposes operator replacements
     drawn from the contracts Registry.
  3. TwinEngine runs a shadow driver alongside the live one; if the
     candidate operator improves drift on shadow, it is committed to the
     live engine. If it regresses, the candidate is rolled back.

This is genuinely novel in three ways:

  * The driver already exposes drift/subdivision, so we don't need a
    separate loss function — drift IS the signal.
  * Capability-indexed Cells let us swap operators by capability name,
    preserving the public driver API.
  * Twin isolation ensures the live engine never sees a candidate that
    hasn't been validated end-to-end.

Editing `minxg.driver` or `minxg.contracts` does NOT affect this module.
Twin only depends on `State`/`Operator`/`EnginePhase` symbols; it
doesn't reach into the engine's internals.
"""
from .failure_tour import FailureTour, Failure
from .field_forge import FieldForge, FieldProposal
from .twin import TwinEngine, TwinOutcome
from .loop import EvolutionLoop, LoopConfig

__all__ = [
    "FailureTour", "Failure",
    "FieldForge", "FieldProposal",
    "TwinEngine", "TwinOutcome",
    "EvolutionLoop", "LoopConfig",
]
