"""tests/test_apk_forge.py — structural + smoke tests for ApkForgeWorker."""

import json
import sys
from pathlib import Path

import pytest

# Add repo root to path so we can import minxg
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.apk_forge import ApkForgeWorker, _WIDGETS
from minxg.base import BaseWorker


def test_worker_subclass_baseworker():
    assert issubclass(ApkForgeWorker, BaseWorker)


def test_worker_attributes():
    w = ApkForgeWorker()
    assert w.worker_id == "apk_forge"
    assert w.version == "0.17.1"


def test_worker_has_14_tools():
    w = ApkForgeWorker()
    # 14 tools: 6 original + 8 expansion
    assert len(w.tools) >= 14


def test_widgets_catalogue():
    assert len(_WIDGETS) >= 10
    names = [e["name"] for e in _WIDGETS]
    assert "md_navigation_drawer" in names
    assert "ft_navigation_destinations" in names


@pytest.mark.asyncio
async def test_apk_plan_valid():
    w = ApkForgeWorker()
    res = await w.call("apk_plan", {
        "manifest": {
            "package": "ai.minxg.demo",
            "title": "Test",
            "version": "0.1.0",
            "presets": ["kivy"],
            "python_version": "3.11",
        }
    })
    assert res["status"] in ("ok", "checks_failed")
    assert "blueprint" in res
    assert res["blueprint"]["package"] == "ai.minxg.demo"


@pytest.mark.asyncio
async def test_apk_plan_bad_package():
    w = ApkForgeWorker()
    res = await w.call("apk_plan", {
        "manifest": {
            "package": "123invalid",
            "title": "Test",
            "version": "0.1",
        }
    })
    assert res["status"] == "checks_failed"


@pytest.mark.asyncio
async def test_apk_scaffold_and_spec(tmp_path):
    w = ApkForgeWorker()
    plan = await w.call("apk_plan", {
        "manifest": {
            "package": "ai.minxg.unit",
            "title": "Unit",
            "version": "0.1.0",
            "presets": ["kivy"],
        }
    })
    bp = plan["blueprint"]
    root = str(tmp_path / "test_app")
    scaffold = await w.call("apk_scaffold", {"root_path": root, "blueprint": bp})
    assert scaffold["status"] == "ok"
    assert Path(root, "main.py").exists()
    assert Path(root, "minxg-manifest.json").exists()

    spec = await w.call("apk_spec", {"root_path": root})
    assert spec["status"] == "ok"
    spec_content = Path(root, "buildozer.spec").read_text()
    assert "title = Unit" in spec_content
    assert "package.name = ai.minxg.unit" in spec_content


@pytest.mark.asyncio
async def test_ui_widgets_list():
    w = ApkForgeWorker()
    res = await w.call("ui_widgets_list", {})
    assert res["status"] == "ok"
    assert res["count"] >= 10


@pytest.mark.asyncio
async def test_ui_template_apply(tmp_path):
    w = ApkForgeWorker()
    root = str(tmp_path / "kivy_app")
    res = await w.call("ui_template_apply", {
        "root_path": root,
        "framework": "kivymd",
        "theme": {"primary": "#FF0000"},
    })
    assert res["status"] == "ok"
    assert res["framework"] == "kivymd"


@pytest.mark.asyncio
async def test_screen_scaffold(tmp_path):
    w = ApkForgeWorker()
    root = str(tmp_path / "flet_app")
    res = await w.call("screen_scaffold", {
        "root_path": root,
        "framework": "flet",
        "screen_name": "settings",
        "components": ["md_navigation_drawer"],
    })
    assert res["status"] == "ok"
    out = Path(root, "app", "settings.py")
    assert out.exists()


@pytest.mark.asyncio
async def test_nav_graph():
    w = ApkForgeWorker()
    res = await w.call("nav_graph_build", {
        "framework": "kivymd",
        "screens": [{"name": "home"}, {"name": "settings"}],
    })
    assert res["status"] == "ok"
    assert "ScreenManager" in res["graph"]


@pytest.mark.asyncio
async def test_apk_icon_generate(tmp_path):
    w = ApkForgeWorker()
    root = str(tmp_path / "icon_app")
    res = await w.call("apk_icon_generate", {
        "root_path": root,
        "accent": "#6200EE",
    })
    assert res["status"] == "ok"
    assert res["bg_bytes"] > 500  # PNG header at least
    assert res["fg_bytes"] > 500


@pytest.mark.asyncio
async def test_apk_asset_pack(tmp_path):
    w = ApkForgeWorker()
    root = str(tmp_path / "asset_app")
    bp = {"package": "a.b", "title": "Pack"}
    res = await w.call("apk_asset_pack", {
        "root_path": root,
        "blueprint": bp,
    })
    assert res["status"] == "ok"
    assert res["wrote"] >= 5


@pytest.mark.asyncio
async def test_apk_dryrun_lint_missing(tmp_path):
    w = ApkForgeWorker()
    root = str(tmp_path / "empty_lint")
    Path(root).mkdir()
    res = await w.call("apk_dryrun_lint", {"root_path": root})
    assert res["blocking"] is True
    assert "buildozer.spec missing" in res["issues"]


@pytest.mark.asyncio
async def test_apk_release_aab_no_buildozer():
    w = ApkForgeWorker()
    res = await w.call("apk_release_aab", {
        "root_path": "/nonexistent",
    })
    assert res["status"] == "disabled"
    assert "buildozer" in res["hint"]


@pytest.mark.asyncio
async def test_concurrent_runner_structure():
    from minxg.five_pillars.transform.concurrent_runner import ConcurrentRunner, _REGISTRY
    w = ConcurrentRunner()
    assert isinstance(w, BaseWorker)
    assert len(_REGISTRY) >= 3


def test_png_emitter():
    from minxg.five_pillars.devtools.apk_forge import _emit_png, _color_solid
    png = _emit_png(32, 32, _color_solid(32, 32, (100, 100, 200)))
    assert len(png) > 100
    assert png[:8] == b"\x89PNG\r\n\x1a\n"