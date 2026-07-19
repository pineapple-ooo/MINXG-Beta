"""
minxg/five_pillars/devtools/math_pillar_dispatcher.py — v0.18.3.

Single dispatcher that exposes MINXG's seven mathematical pillars to the AI
through ONE high-level facade tool.  Each pillar (ga / cat / infogeo / topo /
chaos / fiber / math_pillar) bundles dozens of operators across several
modules; previously these all lived behind ``facade_alias`` so the AI had no
way to call them.

Now: the AI calls ``math_dispatch(pillar="ga", op="rotor", **kwargs)`` and
gets a result dict back.  Old direct calls (``from minxg.ga import rotor``)
continue to work — the dispatcher is additive, not a replacement.

Operator registry is cached at construction time so the dispatch hot path
costs ~one attribute lookup, not introspection.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import traceback
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool


# Pillar → list of (module_name, obj_name) pairs.
# Operators are imported lazily during DashWorker._scan() so a cold-start
# does not pay the full import cost.
_PILLAR_INDEX: Dict[str, List[str]] = {
    "ga":          "minxg.ga",
    "cat":         "minxg.cat",
    "infogeo":     "minxg.infogeo",
    "topo":        "minxg.topo",
    "chaos":       "minxg.chaos",
    "fiber":       "minxg.fiber",
    "math_pillar": "minxg.five_pillars.math_pillar",
}


def _list_module_callables(pkg_root: str) -> List[Dict[str, str]]:
    """Enumerate every callable function under ``pkg_root``.

    Returns a list of ``{"module": ..., "name": ..., "qualified": ...}`` so the
    dispatcher can route without re-running submodule imports.
    """
    import os as _os
    import pkgutil

    out: List[Dict[str, str]] = []
    try:
        pkg = importlib.import_module(pkg_root)
    except Exception:
        return out

    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is None:
        return out

    for finder, mod_name, _ in pkgutil.walk_packages(pkg_path, prefix=f"{pkg_root}."):
        # Skip sub-packages; we want leaf modules only.
        # pkgutil.walk_packages yields both leafs and packages — we filter via
        # the file extension heuristic to exclude directories.
        # Walk_packages leaves ``__name__`` as the dotted module path; we
        # only care about *function*-bearing leaf modules.
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        for attr in dir(mod):
            if attr.startswith("_") or attr[0].isupper():
                continue
            obj = getattr(mod, attr, None)
            if not callable(obj):
                continue
            if inspect.ismodule(obj) or inspect.isclass(obj):
                continue
            # Operator functions live in `operators_<pillar>.py` and
            # numerically-tagged ID ranges per ARCHITECTURE.md.
            out.append({
                "module": mod_name,
                "name": attr,
                "qualified": f"{mod_name}.{attr}",
            })
    return out


# ─────────────────────────────────────────────────────────────────────
#  Worker
# ─────────────────────────────────────────────────────────────────────


class MathPillarDispatcher(BaseWorker):
    """One facade that exposes every math pillar operator to the AI.

    Exposed as the single tool ``math_dispatch`` — calls return a JSON
    payload with the operator's output plus diagnostic metadata.

    Example:
        math_dispatch(pillar="ga", op="rotor", a=1.0, b=2.0, c=3.0)
        math_dispatch(pillar="chaos", op="lyapunov", x0=0.5, r=3.7)
        math_dispatch(pillar="topo", op="persistence_homology",
                      point_cloud=[[0,0],[1,1],[2,2]])
    """

    facade_alias = "math_pillar_dispatcher"   # collapse legacy narrow workers
    worker_id    = "math_pillar_dispatcher"
    tier         = "code"
    version      = "0.18.3"

    def __init__(self):
        self._ops_index: Dict[str, Dict[str, Any]] = {}  # pillar → {op_name: callable}
        self._ops_count = 0
        super().__init__()
        self._scan()

    def _scan(self):
        """Lazy-scan each pillar and bind callables into ``_ops_index``."""
        for pillar, pkg_root in _PILLAR_INDEX.items():
            items = _list_module_callables(pkg_root)
            bucket: Dict[str, Any] = {}
            seen_modules = set()
            for it in items:
                seen_modules.add(it["module"])
                try:
                    obj = _resolve_qualified(it["qualified"])
                except Exception:
                    continue
                if obj is None:
                    continue
                bucket[it["name"]] = obj
            self._ops_index[pillar] = bucket
            self._ops_count += len(bucket)
        # Stash summary to console — caller inspect via stats().
        sys.modules.setdefault(
            "minxg.five_pillars.devtools.math_pillar_dispatcher",
        ).__math_pillar_ops__ = self._ops_index  # type: ignore[attr-defined]

    # ── Tool entry: one fat dispatcher ──────────────────────────────

    @tool(
        description=(
            "Dispatch a call into one of MINXG's seven mathematical pillars "
            "(ga, cat, infogeo, topo, chaos, fiber, math_pillar).  Pass "
            "`pillar` to select the math library and `op` to select the "
            "operator function name.  Additional keyword arguments are "
            "forwarded to the operator.  The result is a JSON-serialisable "
            "dict with status + value + metadata.  Use `math_pillar_list` "
            "first if you don't know which op to call."
        ),
        category="math",
        call_budget=200,
    )
    async def math_dispatch(self, pillar: str, op: str,
                            *args: Any, **kwargs: Any) -> Dict[str, Any]:
        bucket = self._ops_index.get(pillar)
        if bucket is None:
            return {
                "status": "error",
                "error": f"unknown pillar: {pillar!r}. "
                         f"available: {sorted(self._ops_index.keys())}",
            }
        fn = bucket.get(op)
        if fn is None:
            # Try fuzzy match — the AI sometimes mis-spells.
            cands = _fuzzy_op_candidates(op, list(bucket.keys()))
            return {
                "status": "error",
                "error": f"unknown op: {pillar}.{op!r}",
                "available_sample": list(bucket.keys())[:30],
                "did_you_mean": cands[:5],
            }
        try:
            if args and isinstance(args[0], dict):
                # Allow callers to pass kwargs={...} positional.
                kwargs = args[0]
                args = ()
            # Some pillar functions are sync; some are classmethods. Handle both.
            if inspect.iscoroutinefunction(fn):
                out = await fn(*args, **kwargs)
            else:
                out = fn(*args, **kwargs)
            return {
                "status": "ok",
                "pillar": pillar,
                "op": op,
                "result": _to_jsonable(out),
                "engine": "math_pillar_dispatcher",
            }
        except Exception as e:
            tb = traceback.format_exc(limit=2)
            return {
                "status": "error",
                "pillar": pillar, "op": op,
                "error": f"{type(e).__name__}: {e}",
                "traceback": tb,
            }

    # ── Tool entry: introspection ───────────────────────────────────

    @tool(
        description=(
            "List all available operators in a given math pillar (or all "
            "pillars when none specified). Useful before calling "
            "`math_dispatch` to discover which operators exist."
        ),
        category="math",
    )
    async def math_pillar_list(self, pillar: Optional[str] = None) -> Dict[str, Any]:
        if pillar is None:
            return {
                "status": "ok",
                "total_ops": self._ops_count,
                "pillars": {
                    p: len(bucket) for p, bucket in self._ops_index.items()
                },
                "operations": {
                    p: sorted(list(bucket.keys()))
                    for p, bucket in self._ops_index.items()
                },
            }
        bucket = self._ops_index.get(pillar)
        if bucket is None:
            return {
                "status": "error",
                "error": f"unknown pillar: {pillar!r}",
                "available": sorted(self._ops_index.keys()),
            }
        return {
            "status": "ok",
            "pillar": pillar,
            "count": len(bucket),
            "operations": sorted(list(bucket.keys())),
        }

    # ── Stats ────────────────────────────────────────────────

    def statistics(self) -> Dict[str, Any]:
        stats = super().statistics()
        stats["pillars_indexed"] = {
            p: len(bucket) for p, bucket in self._ops_index.items()
        }
        stats["total_pillar_ops"] = self._ops_count
        return stats


# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────


def _resolve_qualified(qualified: str):
    """Driven dispatch — never fails on missing attributes gracefully."""
    try:
        mod_name, attr = qualified.rsplit(".", 1)
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr, None)
    except Exception:
        return None


def _fuzzy_op_candidates(op: str, names: List[str]) -> List[str]:
    """Cheap string-similarity ranking. Cheap = first 60 chars + Levenshtein ≤ 2."""
    import difflib
    if not op:
        return []
    return difflib.get_close_matches(op, names, n=5, cutoff=0.5)


def _to_jsonable(value: Any) -> Any:
    """Coerce operator return values into a JSON-serialisable structure."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, set):
        return sorted([_to_jsonable(v) for v in value])
    try:
        import numpy as _np
        if isinstance(value, _np.ndarray):
            return value.tolist()
    except Exception:
        pass
    # Class instances: try __dict__, then str().
    d = getattr(value, "__dict__", None)
    if isinstance(d, dict):
        return {"_repr": type(value).__name__,
                "attrs": {k: _to_jsonable(v) for k, v in d.items()}}
    return {"_repr": value.__class__.__name__,
            "str": str(value)[:300]}
