"""tests/test_dev_forge.py — structural + smoke tests for QuadForgeWorker + DevForgeWorker alias."""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.dev_forge import (
    QuadForgeWorker, DevForgeWorker,
)
from minxg.base import BaseWorker


def test_worker_subclass_baseworker():
    assert issubclass(QuadForgeWorker, BaseWorker)


def test_dev_forge_alias_is_same_class():
    """DevForgeWorker must remain importable and identical to the canonical name."""
    assert DevForgeWorker is QuadForgeWorker


def test_worker_attributes():
    w = QuadForgeWorker()
    assert w.worker_id == "quad_forge"
    assert w.version == "0.18.1"


def test_worker_has_tier():
    from minxg.tiers import CODE_TIER
    w = QuadForgeWorker()
    assert w.tier == CODE_TIER


def test_worker_has_7_tools():
    w = QuadForgeWorker()
    assert len(w.tools) == 7


def test_tools_have_metadata():
    w = QuadForgeWorker()
    for n, t in w.tools.items():
        assert isinstance(t.description, str) and t.description
        assert t.name == n


@pytest.mark.asyncio
async def test_forge_capabilities_has_28_pairs():
    """4 platforms × on-average 7 frameworks per platform."""
    w = QuadForgeWorker()
    res = await w.call("forge_capabilities", {})
    assert res["status"] == "ok"
    # Spot-check that all four platforms are listed.
    for p in ("android", "harmonyos", "linux", "windows"):
        assert p in res["platforms"]
    # All matrices should have a build_cmd list.
    for m in res["matrix"]:
        assert isinstance(m["platform"], str)
        assert isinstance(m["framework"], str)
        assert isinstance(m["build_cmd"], list)
        assert isinstance(m["exports"], list)


@pytest.mark.asyncio
async def test_forge_plan_android_kivy():
    w = QuadForgeWorker()
    res = await w.call("forge_plan", {
        "manifest": {
            "platform": "android", "framework": "kivy",
            "package": "ai.minxg.demo", "title": "Demo",
            "version": "0.1.0",
        },
    })
    assert res["status"] == "ok"
    assert res["blueprint"]["package"] == "ai.minxg.demo"
    assert "buildozer" in res["blueprint"]["build_cmd"]


@pytest.mark.asyncio
async def test_forge_plan_harmonyos_arkts():
    w = QuadForgeWorker()
    res = await w.call("forge_plan", {
        "manifest": {
            "platform": "harmonyos", "framework": "arkts",
            "package": "com.example", "title": "ArkTSApp",
        },
    })
    assert res["status"] == "ok"
    assert "hap" in res["exports"]


@pytest.mark.asyncio
async def test_forge_plan_windows_winui3():
    w = QuadForgeWorker()
    res = await w.call("forge_plan", {
        "manifest": {
            "platform": "windows", "framework": "winui3",
            "package": "ai.minxg.wapp", "title": "MyWinApp",
        },
    })
    assert res["status"] == "ok"
    assert any("dotnet" in str(p) for p in res["blueprint"]["build_cmd"])


@pytest.mark.asyncio
async def test_forge_plan_unknown_platform():
    w = QuadForgeWorker()
    res = await w.call("forge_plan", {
        "manifest": {"platform": "plan9", "framework": "x"},
    })
    assert res["status"] == "error"


@pytest.mark.asyncio
async def test_forge_scaffold_writes_files():
    w = QuadForgeWorker()
    with tempfile.TemporaryDirectory() as tmp:
        plan = await w.call("forge_plan", {
            "manifest": {
                "platform": "windows", "framework": "winui3",
                "package": "Demo", "title": "Demo",
            },
        })
        bp = plan["blueprint"]
        sc = await w.call("forge_scaffold",
                          {"root_path": tmp, "blueprint": bp})
        assert sc["status"] == "ok"
        assert Path(tmp, "main.cs").exists()
        assert Path(tmp, "minxg-manifest.json").exists()
        manifest = json.loads(Path(tmp, "minxg-manifest.json").read_text())
        assert manifest["platform"] == "windows"


@pytest.mark.asyncio
async def test_forge_legal_notice_explicit():
    w = QuadForgeWorker()
    res = await w.call("forge_legal_notice", {})
    assert res["status"] == "ok"
    assert "academic" in res["academic_use_clause"].lower()


@pytest.mark.asyncio
async def test_forge_export_enumeration():
    w = QuadForgeWorker()
    with tempfile.TemporaryDirectory() as tmp:
        sc = await w.call("forge_scaffold", {
            "root_path": tmp,
            "blueprint": {"platform": "linux", "framework": "pyinstaller",
                          "package": "x", "title": "y"}
        })
        assert sc["status"] == "ok"
        exp = await w.call("forge_export", {
            "root_path": tmp,
            "blueprint": {"platform": "linux", "framework": "pyinstaller",
                          "package": "x", "title": "y"}
        })
        assert exp["status"] == "ok"
        assert any(p.endswith(".py") for p in exp["files"])
