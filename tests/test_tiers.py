"""tests/test_tiers.py — three-tier architecture tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.tiers import (
    AI_TIER, USER_TIER, CODE_TIER, TierRegistry, classify,
)


def test_tier_constants():
    assert AI_TIER == "ai"
    assert USER_TIER == "user"
    assert CODE_TIER == "code"


def test_tier_registry_register():
    r = TierRegistry()
    r.register("a", AI_TIER)
    r.register("b", USER_TIER)
    r.register("c", CODE_TIER)
    assert r.tier_of("a") == "ai"
    assert r.tier_of("b") == "user"
    assert r.tier_of("c") == "code"


def test_tier_registry_rejects_unknown():
    r = TierRegistry()
    try:
        r.register("d", "phantom")
        assert False, "should have raised"
    except ValueError:
        pass


def test_tier_registry_queries_return_sorted():
    r = TierRegistry()
    r.register("zeta", CODE_TIER)
    r.register("alpha", CODE_TIER)
    r.register("beta", AI_TIER)
    r.register("gamma", USER_TIER)
    assert r.ai() == ["beta"]
    assert r.user() == ["gamma"]
    assert r.code() == ["alpha", "zeta"]    # sorted


def test_tier_registry_summary():
    r = TierRegistry()
    r.register("x", AI_TIER)
    r.register("y", CODE_TIER)
    r.register("z", CODE_TIER)
    assert r.summary() == {"ai": 1, "user": 0, "code": 2}


def test_tier_registry_count():
    r = TierRegistry()
    assert r.count(USER_TIER) == 0
    r.register("u1", USER_TIER)
    r.register("u2", USER_TIER)
    assert r.count(USER_TIER) == 2


def test_tier_registry_to_dict():
    r = TierRegistry()
    r.register("k", AI_TIER)
    d = r.to_dict()
    assert d == {"k": "ai"}


# ── Scan the real worker registry ────────────────────────────────────────


def test_scan_real_registry_classifies_workers():
    """Walk the live WorkerRegistry and confirm every worker has a tier."""
    from minxg import WorkerRegistry

    reg = WorkerRegistry()
    # Instantiate the four devtools workers from v0.18.0; they're the
    # only ones guaranteed importable in this environment without
    # pulling in every other pillar.
    from minxg import (AndroidForgeWorker, QuadForgeWorker,
                       DevForgeWorker, DevShellWorker,
                       ReverseStudioWorker, AiToolsWorker, AdbWorker,
                       MathToolsWorker, GeometryWorker,
                       AuditWorker, SelfEvolutionWorker)
    for cls in (AndroidForgeWorker, QuadForgeWorker, DevForgeWorker,
                DevShellWorker, ReverseStudioWorker, AiToolsWorker,
                AdbWorker, MathToolsWorker, GeometryWorker,
                AuditWorker, SelfEvolutionWorker):
        reg.register(cls())

    tr = TierRegistry()
    tr.scan(reg)
    assert tr.tier_of("android_forge") == CODE_TIER
    assert tr.tier_of("quad_forge") == CODE_TIER
    # dev_forge was the v0.18.0 alias; only quad_forge is registered
    # as a real worker, so tier_of("dev_forge") returns None (no
    # worker registered under that id). The heuristic list still has
    # it for classify() fallback routing.
    assert tr.tier_of("dev_shell") == CODE_TIER
    assert tr.tier_of("reverse_studio") == CODE_TIER
    assert tr.tier_of("geometry_tools") == CODE_TIER
    assert tr.tier_of("audit_tools") == CODE_TIER
    assert tr.tier_of("evolution_tools") == "ai"  # SelfEvolution is AI tier
    assert tr.tier_of("ai_tools") == AI_TIER
    assert tr.tier_of("adb") == USER_TIER
    assert tr.tier_of("math_tools") == CODE_TIER


def test_classify_fallback_uses_tier_attribute():
    from minxg import AndroidForgeWorker
    inst = AndroidForgeWorker()
    assert classify(inst) == CODE_TIER
