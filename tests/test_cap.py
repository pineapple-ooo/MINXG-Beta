"""Tests for minxg.cap Corpus-based Capability Registry."""
import pytest
from pathlib import Path
from minxg.cap import (
    CapManifest, CapChange,
    CapModule,
    scan_file, scan_tree,
    get_manifest,
)
from minxg.cap import cli
from minxg.cap import registry


def test_scan_file_extracts_both_tags(tmp_path):
    fp = tmp_path / "x.py"
    fp.write_text(
        "minxg.cap.provides: foo, foo.bar\n"
        "minxg.cap.requires: net.http\n"
        "import sys\n"
    )
    record = scan_file(fp)
    assert record is not None
    assert record.provides == ("foo", "foo.bar")
    assert record.requires == ("net.http",)


def test_scan_file_returns_none_when_no_tags(tmp_path):
    fp = tmp_path / "x.py"
    fp.write_text('"""ordinary docstring"""\n')
    assert scan_file(fp) is None


def test_scan_file_only_provides(tmp_path):
    fp = tmp_path / "x.py"
    fp.write_text(
        "minxg.cap.provides: alone\n"
        "import sys\n"
    )
    record = scan_file(fp)
    assert record is not None
    assert record.provides == ("alone",)
    assert record.requires == ()


def test_scan_tree_collects_in_path_order(tmp_path):
    (tmp_path / "a.py").write_text('minxg.cap.provides: alpha\nimport sys\n')
    (tmp_path / "b.py").write_text('minxg.cap.provides: beta\nimport sys\n')
    (tmp_path / "nope.py").write_text('"""plain"""\n')
    records = scan_tree(tmp_path)
    assert [r.provides for r in records] == [("alpha",), ("beta",)]


def test_manifest_what_provides_returns_sorted_paths():
    manifest = CapManifest()
    manifest.add(CapModule(path="/c.py", provides=("z",)))
    manifest.add(CapModule(path="/a.py", provides=("z",)))
    assert manifest.what_provides("z") == ["/a.py", "/c.py"]


def test_manifest_what_requires_returns_sorted_paths():
    manifest = CapManifest()
    manifest.add(CapModule(path="/leaf.py", requires=("driver.step",)))
    assert manifest.what_requires("driver.step") == ["/leaf.py"]


def test_manifest_dependencies_of_is_transitive():
    manifest = CapManifest()
    manifest.add(CapModule(path="/top.py", requires=("middleware.auth",)))
    manifest.add(CapModule(
        path="/mid.py", provides=("middleware.auth",), requires=("driver.step",)))
    manifest.add(CapModule(path="/bot.py", provides=("driver.step",)))
    closure = manifest.dependencies_of("/top.py")
    assert closure == {"driver.step", "middleware.auth"}


def test_manifest_check_detects_missing_provider():
    manifest = CapManifest()
    manifest.add(CapModule(path="/leaf.py", requires=("missing.cap",)))
    issues = manifest.check()
    assert any(i.kind == "missing_provider" for i in issues)


def test_manifest_check_reports_unused_provider():
    manifest = CapManifest()
    manifest.add(CapModule(path="/provider.py", provides=("nobody.uses",)))
    issues = manifest.check()
    assert any(i.kind == "unused_provider" for i in issues)


def test_manifest_check_passes_when_balanced():
    manifest = CapManifest()
    manifest.add(CapModule(path="/producer.py", provides=("shared",)))
    manifest.add(CapModule(path="/consumer.py", requires=("shared",)))
    assert manifest.check() == []


def test_manifest_changes_since_reports_added_and_removed():
    base = {
        "/a.py": (("p",), ("r",)),
        "/b.py": ((), ("r",)),
    }
    manifest = CapManifest()
    manifest.add(CapModule(path="/a.py", provides=("p", "p2"), requires=("r",)))
    manifest.add(CapModule(path="/b.py", provides=("q",), requires=()))
    changes = manifest.changes_since(base)
    paths = {c.path: c for c in changes}
    assert paths["/a.py"].added_provides == ("p2",)


def test_cap_change_is_empty():
    assert CapChange(path="/x.py").is_empty
    assert not CapChange(path="/x.py", added_provides=("foo",)).is_empty


def test_cli_provides_runs(capsys):
    registry._default = None
    manifest = CapManifest()
    manifest.add(CapModule(path="/y.py", provides=("hello.world",)))
    registry._default = manifest
    rc = cli.main(["provides", "hello.world"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "/y.py" in captured.out


def test_cli_check_returns_zero_when_clean(capsys):
    manifest = CapManifest()
    manifest.add(CapModule(path="/p.py", provides=("a",)))
    manifest.add(CapModule(path="/c.py", requires=("a",)))
    registry._default = manifest
    rc = cli.main(["check"])
    assert rc == 0


def test_cli_check_returns_nonzero_on_missing(capsys):
    manifest = CapManifest()
    manifest.add(CapModule(path="/c.py", requires=("a",)))
    registry._default = manifest
    rc = cli.main(["check"])
    assert rc == 1


def test_get_manifest_scans_caller_module():
    from minxg.cap import registry
    registry.reset_manifest()
    manifest = get_manifest()
    paths = {m.path for m in manifest.modules.values()}
    assert any("/minxg/cap/" in p for p in paths), \
        f"expected cap module in scanned tree, got {list(paths)[:5]}"
