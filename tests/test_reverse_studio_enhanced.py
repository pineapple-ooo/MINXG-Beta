"""tests/test_reverse_studio_enhanced.py -- Tests for MIT-licensed 2改 enhanced reverse tools."""

import asyncio
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.reverse_studio import ReverseStudioWorker, LEGAL_NOTICE


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture
def worker():
    return ReverseStudioWorker()


@pytest.fixture
def fake_apk(tmp_path):
    """Create a minimal fake APK for testing."""
    apk = tmp_path / "test.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        # Fake manifest with security issues
        zf.writestr("AndroidManifest.xml",
                     '<manifest android:allowBackup="true" '
                     'android:debuggable="true">'
                     '<activity android:exported="true" />'
                     "</manifest>")
        # Fake JS with WebView issues
        zf.writestr("assets/webview.js",
                     "webView.setJavaScriptEnabled(true); "
                     "webView.addJavascriptInterface(bridge, 'Bridge');")
        # Fake config with secret
        zf.writestr("res/config.properties",
                     "api_key=AKIAIOSFODNN7EXAMPLE\n"
                     "password=secret12345678")
    return str(apk)


def test_worker_id(worker):
    assert worker.worker_id == "reverse_studio"


def test_secret_scan(worker, fake_apk):
    r = _run(worker.reverse_secret_scan(fake_apk))
    assert r["status"] == "ok"
    assert r["total_secrets"] >= 1
    assert "source" in r
    assert "MIT" in r["source"]


def test_manifest_audit(worker, fake_apk):
    r = _run(worker.reverse_manifest_audit(fake_apk))
    assert r["status"] == "ok"
    assert r["total_issues"] >= 2  # allowBackup + debuggable
    # Should detect debuggable as critical
    severities = [i["severity"] for i in r["issues"]]
    assert "critical" in severities
    assert "MIT" in r["source"]


def test_webview_scan(worker, fake_apk):
    r = _run(worker.reverse_webview_scan(fake_apk))
    assert r["status"] == "ok"
    assert r["total_findings"] >= 2  # JS enabled + addJavascriptInterface
    assert "MIT" in r["source"]


def test_full_audit(worker, fake_apk):
    r = _run(worker.reverse_full_audit(fake_apk))
    assert r["status"] == "ok"
    assert r["total_issues"] >= 3
    assert "sources" in r
    assert len(r["sources"]) == 3
    # All sources should mention MIT
    for src in r["sources"]:
        assert "MIT" in src


def test_missing_apk(worker):
    r = _run(worker.reverse_secret_scan("/nonexistent.apk"))
    assert r["status"] == "error"


def test_legal_notice_in_every_tool(worker, fake_apk):
    """Every enhanced tool must return legal_disclaimer."""
    for method in ["reverse_secret_scan", "reverse_manifest_audit",
                   "reverse_webview_scan", "reverse_full_audit"]:
        r = _run(getattr(worker, method)(fake_apk))
        assert r["status"] == "ok"
        assert "legal_disclaimer" in r
        assert LEGAL_NOTICE in r["legal_disclaimer"]
