"""DatalogWorker — symbolic graph/logic reasoning via clingo (or pyDatalog).

Real-world responsibilities inside MINXG:

* Self-evolution engine — prove capability closure under a Cell.
  Concretely: given a set of registered capabilities, ask Datalog
  ``reachable_cap(X, Y)`` whether every prerequisite chain has a path;
  this guards against accepting a proposal that silently breaks a Cell
  composition.
* Twin engine — resolve ``python_to_rust`` AST correspondence rules:
  declare a node/edge relation and let Datalog enumerate valid rewrites
  (far simpler to express in Datalog than Python loops over typed trees).
* Capabilities manifest — answer capability queries like
  "can this worker satisfy request X given capability Y?" with a
  declarative, deduplicated response (clauses unify; duplicates vanish).

Public tools: ``datalog_run_rules``, ``datalog_graph_reachable``,
``datalog_cycle_check``, ``datalog_set_intersection``,
``datalog_subset_check``, ``datalog_demo``.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool

import sys as _sys
_ADAPTER = _sys.modules.get("minxg.contracts.runtime.datalog")


class DatalogWorker(BaseWorker):
    worker_id = "datalog_logic"
    version = "0.16.0"

    @tool(description="Run arbitrary Datalog / ASP rules and return solver output.",
          category="logic")
    async def datalog_run_rules(self, code: str) -> Dict[str, Any]:
        if not code.strip():
            return self._bad_input("code cannot be empty", {})
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("datalog_run_rules", code[:40])
        return await self._invoke_async({"code": code})

    @tool(description="Compute graph reachability via clingo transitive closure.",
          category="logic")
    async def datalog_graph_reachable(
        self,
        edges: List[List[str]],
    ) -> Dict[str, Any]:
        """``edges`` is a list of [from,to] pairs.

        Returns: dict with ``tclose`` (list of reachable pairs),
        ``strong_components`` (Datalog's dominated-component analysis).
        """
        if not edges:
            return self._bad_input("edges cannot be empty", {})
        node_clauses = "\n".join(f"node({a}). node({b})." for a, b in edges)
        edge_clauses = "\n".join(f"edge({a},{b})." for a, b in edges)
        user_code = f"{node_clauses}\n{edge_clauses}"
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("datalog_graph_reachable",
                                  f"{len(edges)} edges")
        return await self._invoke_async({"code": user_code})

    @tool(description="Detect cycles in a directed graph.",
          category="logic")
    async def datalog_cycle_check(
        self,
        edges: List[List[str]],
    ) -> Dict[str, Any]:
        if not edges:
            return {"status": "ok", "language": "datalog",
                    "cycles": [], "cycle_count": 0,
                    "hint": "Empty graph — vacuously acyclic"}
        node_clauses = "\n".join(f"node({a}). node({b})." for a, b in edges)
        edge_clauses = "\n".join(f"edge({a},{b})." for a, b in edges)
        user_code = (f"{node_clauses}\n{edge_clauses}\n"
                     "% Cycle detection query\n"
                     "#show cycle/1.\n")
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("datalog_cycle_check",
                                  f"{len(edges)} edges")
        return await self._invoke_async({"code": user_code})

    @tool(description="Compute set intersection of two ordered lists.",
          category="logic")
    async def datalog_set_intersection(
        self,
        a: List[str],
        b: List[str],
    ) -> Dict[str, Any]:
        if not a or not b:
            return self._bad_input("both lists must be non-empty", {})
        # Wrap two sets as edges into the bridge's ``in_set`` predicate.
        a_clauses = "\n".join(f'set_element("a",X) :- X = "{x}".' for x in a)
        b_clauses = "\n".join(f'set_element("b",X) :- X = "{x}".' for x in b)
        user_code = (
            f"{a_clauses}\n{b_clauses}\n"
            '#show in_intersection/3.\n'
        )
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("datalog_set_intersection",
                                  f"|a|={len(a)}, |b|={len(b)}")
        return await self._invoke_async({"code": user_code})

    @tool(description="Check A ⊆ B (pure data, no engine required).",
          category="logic")
    async def datalog_subset_check(
        self,
        a: List[str],
        b: List[str],
    ) -> Dict[str, Any]:
        """Subset check is a pure-Python computation; doesn't need the engine.

        Kept here as a tool so tests can swap engineless paths and so
        users have a uniform tool surface (``datalog_.*``).
        """
        set_a, set_b = set(a), set(b)
        missing = sorted(set_a - set_b)
        return {
            "status": "ok" if not missing else "subset_violation",
            "language": "datalog",
            "tool": "datalog_subset_check",
            "subset": not missing,
            "missing": missing,
            "a_size": len(set_a),
            "b_size": len(set_b),
        }

    @tool(description="Run the shipped demo rules (transitive closure example).",
          category="logic")
    async def datalog_demo(self) -> Dict[str, Any]:
        adapter_status = self._status()
        if adapter_status != "available":
            return self._disabled("datalog_demo", "built-in demo")
        return await self._invoke_async({"mode": "demo"})

    # ── Helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _status() -> str:
        return getattr(_ADAPTER, "ADAPTER_STATUS", "disabled")

    @staticmethod
    async def _invoke_async(payload: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        if _ADAPTER is None:
            return {
                "status": "disabled",
                "language": "datalog",
                "tool": "datalog_run_rules",
                "hint": "Datalog adapter module not importable; check site-packages.",
            }
        return await loop.run_in_executor(
            None, lambda: _ADAPTER.invoke(payload)
        )

    @staticmethod
    def _disabled(verb: str, example: str) -> Dict[str, Any]:
        return {
            "status": "disabled",
            "language": "datalog",
            "tool": verb,
            "hint": (
                "Datalog runtime not installed. To enable: install clingo "
                "(apt install clingo / pkg install clingo or pip install "
                "pyDatalog). Then: minxg runtime-install datalog --apply. "
                f"Was attempting: {example}"
            ),
        }

    @staticmethod
    def _bad_input(why: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "error",
            "language": "datalog",
            "tool": "input_validation",
            "stderr": why,
            "context": context,
        }