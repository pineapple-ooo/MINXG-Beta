"""minxg/tiers/__init__.py — Three-tier architecture for MINXG.

The three-tier model organises every worker into exactly one
"tier" — the layer it serves in the overall AI-user-compute
stack.  Each tier carries a distinct responsibility and its
public documentation contract is explicit so nobody ever
asks "what does this worker do?"

Tiers
-----

AI 层 (ai)        — workers that **generate, reason, plan**.
                     They produce language, code, decisions,
                     or creative content.  Think of them as the
                     "brain" side of the platform.

用户层 (user)      — workers that **interact with a human or
                     a human-facing tool**.  They talk to
                     keyboards, screens, ADB devices, web
                     browsers, push notifications.  Think of
                     them as the "hands and eyes" of the
                     platform.

代码运算层 (code)  — workers that **execute deterministic
                     computation**.  They run native math
                     kernels, compile, build, lint, transpile,
                     hash, encrypt, or invoke foreign-language
                     runtimes (Rust/Julia/R/Datalog/Wasm).
                     Think of them as the "engine" that
                     powers both ai and user tiers.

Every worker in the project is tagged with exactly one
``tier`` attribute.  The tier registry (`TierRegistry`)
provides discovery methods so the CLI, gateway, and tests
can query "what is in the code tier?" without iterating
the whole worker list.

Usage
-----

    from minxg.tiers import AI_TIER, USER_TIER, CODE_TIER, classify, TierRegistry

    reg = TierRegistry()
    reg.scan(...)            # auto-tags workers by their ``.tier`` attr
    reg.ai()                 # -> list of AI-tier worker ids
    reg.summary()            # -> {ai:N, user:M, code:K}

"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ── Tier tag constants ──────────────────────────────────────────
AI_TIER = "ai"
USER_TIER = "user"
CODE_TIER = "code"

ALL_TIERS = (AI_TIER, USER_TIER, CODE_TIER)

# ── Tier registry ───────────────────────────────────────────────


class TierRegistry:
    """Lightweight registry that maps worker_id -> tier label.

    Populated by calling ``scan(registry)`` with a
    ``WorkerRegistry`` instance — it reads ``.tier`` from
    each worker.
    """

    def __init__(self):
        self._map: Dict[str, str] = {}

    def register(self, worker_id: str, tier: str):
        if tier not in ALL_TIERS:
            raise ValueError(f"unknown tier {tier!r}")
        self._map[worker_id] = tier

    def scan(self, worker_registry):
        """Walk every registered worker and read its .tier attribute."""
        from minxg.base import BaseWorker, WorkerRegistry
        for wid, w in worker_registry.workers.items():
            tier = getattr(w, "tier", None)
            if tier and tier in ALL_TIERS:
                self._map[wid] = tier
            else:
                log.warning("worker %r missing .tier — unclassified", wid)
        log.info(
            "TierRegistry scanned %d workers → ai=%d user=%d code=%d",
            len(worker_registry.workers),
            self.count(AI_TIER),
            self.count(USER_TIER),
            self.count(CODE_TIER),
        )

    # ── query helpers ────────────────────────────────────────
    def tier_of(self, worker_id: str) -> Optional[str]:
        return self._map.get(worker_id)

    def ai(self) -> List[str]:
        return sorted(k for k, v in self._map.items() if v == AI_TIER)

    def user(self) -> List[str]:
        return sorted(k for k, v in self._map.items() if v == USER_TIER)

    def code(self) -> List[str]:
        return sorted(k for k, v in self._map.items() if v == CODE_TIER)

    def count(self, tier: str) -> int:
        return sum(1 for v in self._map.values() if v == tier)

    def summary(self) -> Dict[str, int]:
        return {
            "ai": self.count(AI_TIER),
            "user": self.count(USER_TIER),
            "code": self.count(CODE_TIER),
        }

    def to_dict(self) -> Dict[str, str]:
        return dict(self._map)


def classify(worker) -> str:
    """Guess a tier from a worker object, falling back to CODE_TIER."""
    import inspect

    # Explicit .tier attribute wins.
    if hasattr(worker, "tier") and getattr(worker, "tier") in ALL_TIERS:
        return worker.tier

    wid = getattr(worker, "worker_id", "unknown")

    # ── heuristic by worker_id prefix ──────────────────────────
    # These heuristics are brittle by design — every new worker
    # gets an explicit .tier in its class definition.  The
    # fallback exists ONLY for the initial migration.
    _AI_IDS = {"ai_tools", "text_kit", "ml_tools", "benchmark_tools",
                "template_tools", "i18n_tools", "encoding_tools"}
    _USER_IDS = {"adb_tools", "root_tools", "screen_tools",
                 "notify_tools", "fs_io", "fs_copy",
                 "fs_search", "media_tools", "web_tools",
                 "files_ext", "root_ext", "adb_ext",
                 "db_tools"}
    _CODE_IDS = {"math_tools", "crypto_tools", "version_tools",
                 "data_tools", "operator_tools", "dev_tools",
                 "process_tools", "sh_exec", "sh_query",
                 "limits_lock", "limits_break",
                 "julia_tools", "r_tools", "datalog_tools",
                 "wasm_tools", "android_forge", "quad_forge",
                 "dev_forge",  # back-compat alias routing
                 "geometry_tools", "audit_tools",
                 "evolution_tools",
                 "text_tools",
                 "string_tools", "datetime_tools",
                 "state_session", "state_machine",
                 "concurrent_runner", "platform_tools",
                 "archive_tools"}

    if wid in _AI_IDS or wid.startswith(("ai_", "ml_")):
        return AI_TIER
    if wid in _USER_IDS or wid.startswith(("adb_", "root_", "screen_", "notify_")):
        return USER_TIER
    return CODE_TIER