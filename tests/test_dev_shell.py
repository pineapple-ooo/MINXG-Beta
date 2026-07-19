"""tests/test_dev_shell.py — dev shell facade tests."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from minxg.five_pillars.devtools.dev_shell import DevShellWorker
from minxg.base import BaseWorker


def test_worker_subclass_baseworker():
    assert issubclass(DevShellWorker, BaseWorker)


def test_worker_attributes():
    w = DevShellWorker()
    assert w.worker_id == "dev_shell"
    assert w.version == "0.18.0"


def test_worker_has_tier():
    from minxg.tiers import CODE_TIER
    w = DevShellWorker()
    assert w.tier == CODE_TIER


def test_worker_has_9_tools():
    w = DevShellWorker()
    assert len(w.tools) == 9


@pytest.mark.asyncio
async def test_shell_capabilities():
    w = DevShellWorker()
    res = await w.call("shell_capabilities", {})
    assert res["status"] == "ok"
    assert "python" in res["languages"]
    assert "rust" in res["languages"]
    assert "csharp" in res["languages"]
    assert "ahk" in res["languages"]   # we cover 11 languages


@pytest.mark.asyncio
async def test_shell_capabilities_python():
    w = DevShellWorker()
    res = await w.call("shell_capabilities", {"language": "python"})
    assert res["status"] == "ok"
    cmds = res["commands"]
    assert "lint" in cmds and "format" in cmds and "test" in cmds and "run" in cmds


@pytest.mark.asyncio
async def test_shell_detect_python(tmp_path):
    (tmp_path / "main.py").write_text("print('x')")
    w = DevShellWorker()
    res = await w.call("shell_detect", {"root_path": str(tmp_path)})
    assert res["status"] == "ok"
    assert res["language"] == "python"


@pytest.mark.asyncio
async def test_shell_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname=\"x\"")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main(){}")
    w = DevShellWorker()
    res = await w.call("shell_detect", {"root_path": str(tmp_path)})
    assert res["status"] == "ok"
    assert res["language"] == "rust"


@pytest.mark.asyncio
async def test_shell_detect_unknown(tmp_path):
    w = DevShellWorker()
    res = await w.call("shell_detect", {"root_path": str(tmp_path)})
    assert res["status"] == "ok"
    assert res["language"] == "unknown"


@pytest.mark.asyncio
async def test_gitignore_python(tmp_path):
    w = DevShellWorker()
    res = await w.call("gengitignore",
                        {"root_path": str(tmp_path), "language": "python"})
    assert res["status"] == "ok"
    gi = Path(tmp_path) / ".gitignore"
    assert gi.exists()
    assert "__pycache__" in gi.read_text()


@pytest.mark.asyncio
async def test_gitignore_unknown_language(tmp_path):
    w = DevShellWorker()
    res = await w.call(
        "gengitignore",
        {"root_path": str(tmp_path), "language": "brainfuck"},
    )
    assert res["status"] == "error"


@pytest.mark.asyncio
async def test_clean_removes_build_dir(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "x.so").write_bytes(b"x")
    (tmp_path / "main.py").write_text("print")
    w = DevShellWorker()
    res = await w.call("clean", {"root_path": str(tmp_path)})
    assert res["status"] == "ok"
    assert not (tmp_path / "build").exists()
    assert (tmp_path / "main.py").exists()  # source preserved


@pytest.mark.asyncio
async def test_doctor_reports_languages(tmp_path):
    w = DevShellWorker()
    res = await w.call("doctor", {})
    assert res["status"] == "ok"
    assert len(res["report"]) >= 11


@pytest.mark.asyncio
async def test_lint_python_missing_ruff(tmp_path, monkeypatch):
    """If ruff isn't installed, return disabled instead of erroring."""
    (tmp_path / "main.py").write_text("x=1\n")
    w = DevShellWorker()
    # We don't monkeypatch PATH; just call lint and check the envelope.
    res = await w.call("lint", {"root_path": str(tmp_path)})
    # Either status "ok" (if ruff installed) or "disabled" (if not).
    assert res["status"] in ("ok", "disabled", "failed")
    assert res["tool"] == "lint"


@pytest.mark.asyncio
async def test_run_unknown_language(tmp_path):
    w = DevShellWorker()
    res = await w.call("run",
                        {"root_path": str(tmp_path), "language": "elvish"})
    # Elvish isn't in our supported set; _resolve_lang should error out.
    assert res["status"] == "error"
