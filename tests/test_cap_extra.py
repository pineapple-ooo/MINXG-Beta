"""Extra coverage for minxg.cap — scanner, manifest, and CLI."""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from minxg.cap import (
    CapManifest,
    CapModule,
    CapChange,
    scan_tree,
    scan_file,
)
from minxg.cap import cli


def test_cap_module_imports_cleanly():
    import importlib
    import minxg.cap
    importlib.reload(minxg.cap)


def test_scan_tree_collects_files_in_path_order(tmp_path):
    (tmp_path / "a.py").write_text("minxg.cap.provides: alpha\nimport sys\n")
    (tmp_path / "b.py").write_text("minxg.cap.provides: beta\nimport sys\n")
    (tmp_path / "ignored.txt").write_text("not python\n")
    records = scan_tree(tmp_path)
    names = [r.path.split("/")[-1] for r in records]
    assert names == ["a.py", "b.py"]


def test_manifest_what_provides_returns_sorted_paths():
    manifest = CapManifest()
    manifest.add(CapModule(path="/z.py", provides=("p",)))
    manifest.add(CapModule(path="/a.py", provides=("p",)))
    manifest.add(CapModule(path="/m.py", provides=("q",)))
    assert manifest.what_provides("p") == ["/a.py", "/z.py"]
    assert manifest.what_provides("q") == ["/m.py"]


def test_manifest_check_passes_when_balanced():
    manifest = CapManifest()
    manifest.add(CapModule(path="/producer.py", provides=("shared.cap",)))
    manifest.add(CapModule(path="/consumer.py", requires=("shared.cap",)))
    issues = manifest.check()
    assert issues == []


def test_manifest_changes_since_reports_added_and_removed():
    base = {
        "/a.py": (("p",), ("r",)),
        "/b.py": ((), ("r",)),
    }
    manifest = CapManifest()
    manifest.add(CapModule(path="/a.py", provides=("p", "p2"), requires=("r",)))
    manifest.add(CapModule(path="/b.py", provides=("q",), requires=()))
    manifest.add(CapModule(path="/c.py", provides=("new",), requires=()))
    changes = manifest.changes_since(base)
    by_path = {c.path: c for c in changes}
    assert "/a.py" in by_path
    assert by_path["/a.py"].added_provides == ("p2",)
    assert "/b.py" in by_path
    assert by_path["/b.py"].removed_requires == ("r",)
    assert "/c.py" in by_path
    assert by_path["/c.py"].added_provides == ("new",)


def test_manifest_changes_since_detects_removed_module():
    base = {
        "/gone.py": (("old",), ()),
    }
    manifest = CapManifest()
    changes = manifest.changes_since(base)
    by_path = {c.path: c for c in changes}
    assert "/gone.py" in by_path
    assert by_path["/gone.py"].removed_provides == ("old",)


def test_cli_cap_check_returns_zero_on_clean_tree_subprocess(tmp_path):
    """Run the cap CLI in a subprocess with a pre-seeded clean manifest."""
    script = tmp_path / "run_check.py"
    script.write_text(textwrap.dedent("""
        import sys
        from minxg.cap.registry import _default
        from minxg.cap import CapManifest, CapModule, cli
        manifest = CapManifest()
        manifest.add(CapModule(path='/p.py', provides=('clean.cap',)))
        manifest.add(CapModule(path='/c.py', requires=('clean.cap',)))
        import minxg.cap.registry as reg
        reg._default = manifest
        sys.exit(cli.main(['check']))
    """))
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"expected rc=0, got {proc.returncode}\\nstdout: {proc.stdout}\\nstderr: {proc.stderr}"
    )


def test_cap_change_is_empty_when_nothing_changed():
    change = CapChange(path="/x.py")
    assert change.is_empty
    full = CapChange(
        path="/x.py",
        added_provides=("a",),
        removed_provides=("b",),
        added_requires=("c",),
        removed_requires=("d",),
    )
    assert not full.is_empty


def test_scan_file_returns_none_for_non_python():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"plain text")
        path = Path(f.name)
    try:
        assert scan_file(path) is None
    finally:
        path.unlink()
