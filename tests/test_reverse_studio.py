"""tests/test_reverse_studio.py — academic-only reverse engineering studio tests."""

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.reverse_studio import (
    ReverseStudioWorker, LEGAL_NOTICE,
)
from minxg.base import BaseWorker


def test_worker_subclass_baseworker():
    assert issubclass(ReverseStudioWorker, BaseWorker)


def test_worker_attributes():
    w = ReverseStudioWorker()
    assert w.worker_id == "reverse_studio"
    assert w.version == "0.18.0"


def test_worker_has_tier():
    from minxg.tiers import CODE_TIER
    w = ReverseStudioWorker()
    assert w.tier == CODE_TIER


def test_worker_has_11_tools():
    w = ReverseStudioWorker()
    assert len(w.tools) == 11


def test_legal_notice_contains_required_phrases():
    """The legal notice MUST mention all of these — by contract."""
    assert "ACADEMIC" in LEGAL_NOTICE
    assert "INTEROPERABILITY" in LEGAL_NOTICE
    assert "2009/24/EC" in LEGAL_NOTICE   # EU directive
    assert "1201(f)" in LEGAL_NOTICE      # US DMCA carve-out
    assert "MINXG" in LEGAL_NOTICE        # project name
    assert "disclaim" in LEGAL_NOTICE.lower()  # liability disclaimer


@pytest.mark.asyncio
async def test_reverse_legal_notice_emitted():
    w = ReverseStudioWorker()
    res = await w.call("reverse_legal_notice", {})
    assert res["status"] == "ok"
    assert res["legal_notice"] == LEGAL_NOTICE


@pytest.mark.asyncio
async def test_reverse_capabilities_list():
    w = ReverseStudioWorker()
    res = await w.call("reverse_capabilities", {})
    assert res["status"] == "ok"
    assert res["count"] >= 6
    assert res["license"] == LEGAL_NOTICE


def _fake_apk(tmp: Path) -> Path:
    apk = tmp / "fake.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("AndroidManifest.xml",
                    b'<?xml package="ai.test.demo" versionCode="42" '
                    b'versionName="1.2.3" />')
        zf.writestr("classes.dex", b"dex\n" + b"\x00" * 108)
        zf.writestr("res/drawable/icon.png", b"\xff\xd8")
        zf.writestr("res/layout/main.xml", b"<x/>")
    return apk


@pytest.mark.asyncio
async def test_reverse_inspect_attaches_legal_notice(tmp_path):
    w = ReverseStudioWorker()
    apk = _fake_apk(tmp_path)
    res = await w.call("reverse_inspect", {"apk_path": str(apk)})
    assert res["status"] == "ok"
    assert res["legal_disclaimer"] == LEGAL_NOTICE
    assert res["manifest"]["package"] == "ai.test.demo"


@pytest.mark.asyncio
async def test_reverse_hash_attaches_legal_notice(tmp_path):
    w = ReverseStudioWorker()
    apk = _fake_apk(tmp_path)
    res = await w.call("reverse_hash", {"apk_path": str(apk)})
    assert res["status"] == "ok"
    assert res["legal_disclaimer"] == LEGAL_NOTICE
    assert isinstance(res["sha256"], str) and len(res["sha256"]) == 64


@pytest.mark.asyncio
async def test_reverse_strings_attaches_legal_notice(tmp_path):
    w = ReverseStudioWorker()
    apk = _fake_apk(tmp_path)
    res = await w.call("reverse_strings", {"apk_path": str(apk)})
    assert res["status"] == "ok"
    assert res["legal_disclaimer"] == LEGAL_NOTICE
    assert res["count"] >= 1


@pytest.mark.asyncio
async def test_reverse_diff_manifest(tmp_path):
    w = ReverseStudioWorker()
    a = {"package": "x", "version": "1"}
    b = {"package": "x", "version": "2", "extra": True}
    res = await w.call("reverse_manifest_diff",
                        {"manifest_a": a, "manifest_b": b})
    assert res["status"] == "ok"
    assert "extra" in res["added"]
    assert "version" in res["changed"]


@pytest.mark.asyncio
async def test_reverse_inspect_refuses_missing_file(tmp_path):
    w = ReverseStudioWorker()
    res = await w.call("reverse_inspect",
                        {"apk_path": str(tmp_path / "nope.apk")})
    assert res["status"] == "error"
    assert res["legal_disclaimer"] == LEGAL_NOTICE


@pytest.mark.asyncio
async def test_reverse_inspect_rejects_non_zip(tmp_path):
    w = ReverseStudioWorker()
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"not a zip")
    res = await w.call("reverse_inspect", {"apk_path": str(raw)})
    assert res["status"] == "error"
    assert res["legal_disclaimer"] == LEGAL_NOTICE
