"""Per-agent iteration budget — thread-safe consume/refund counter.

Each ``Orchestrator`` instance gets an ``IterationBudget`` to prevent
infinite tool-calling loops. The default cap comes from ``max_iterations``
(default 90). Subagents get independent budgets.

``execute_code`` iterations are refunded via :meth:`refund` so they don't
eat into the budget.
"""

from __future__ import annotations

import threading


class IterationBudget:
    """Thread-safe iteration counter for an agent.

    Each agent gets its own ``IterationBudget``. The cap is set at
    ``max_iterations`` (default 90).

    ``execute_code`` (programmatic tool calling) iterations are refunded via
    :meth:`refund` so they don't eat into the budget.
    """

    def __init__(self, max_total: int):
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        """Try to consume one iteration.  Returns True if allowed."""
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        """Give back one iteration (e.g. for execute_code turns)."""
        with self._lock:
            if self._used > 0:
                self._used -= 1

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.max_total - self._used)


__all__ = ["IterationBudget"]
