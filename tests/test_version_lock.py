"""tests/test_version_lock.py — cross-file version invariants.

The MINXG version is a *single source of truth* in ``minxg/_version.py``.
From there it propagates to:

* ``pyproject.toml``  — consumed via ``[project] dynamic = ["version"]``
                        and ``[tool.setuptools.dynamic] version.attr``.
* ``minxg/__init__.py``  — re-exported as ``__version__``.
* Doc surfaces (README banner / pip-install line, CHANGELOG top entry,
  DEVELOPER publishing checklist) — those MUST be kept in sync manually,
  this test just catches drift.

Before v0.13.2 each consumer held its own literal copy of the version and
this guard fired whenever any one of them drifted. Now that the code
locations pull from ``minxg._version``, the test was rewritten in two
pieces:

* ``test_runtime_singularity`` — code paths all read the same value.
* ``test_docs_echo_singular_value`` — doc surfaces echo the SSoT.

Both pieces must pass. If either does not, releases silently drift.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
VERSION_PY = REPO / "minxg" / "_version.py"
PYPROJECT = REPO / "pyproject.toml"
INIT_PY = REPO / "minxg" / "__init__.py"
README = REPO / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"
DEVELOPER = REPO / "DEVELOPER.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ssot() -> str:
    """Read the single source of truth from ``minxg/_version.py``.

    Falls back to importing it (catches the case where someone renamed
    the file or moved the constant location).
    """
    text = _read(VERSION_PY)
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.M)
    assert m, f"{VERSION_PY} missing `VERSION = \"…\"` — single source of truth broken"
    return m.group(1)


def _ssot_imported() -> str:
    sys.path.insert(0, str(REPO))
    try:
        import minxg._version as v   # noqa: PLC0415 — intentional late import
        return v.VERSION
    finally:
        sys.path.pop(0)


def test_ssot_import_matches_literal():
    """The literal ``VERSION = "0.17.1"`` and the runtime import must agree.

    Otherwise ``pyproject.toml`` (which reads ``minxg._version.VERSION``
    via setuptools dynamic) would build a wheel with the wrong number.
    """
    assert _ssot() == _ssot_imported(), (
        f"_version.py literal says {_ssot()!r} but runtime import says "
        f"{_ssot_imported()!r} — SSoT is internally inconsistent"
    )


def test_pyproject_consumes_ssot():
    """``pyproject.toml`` must declare the version dynamic and pin the attr."""
    text = _read(PYPROJECT)
    assert re.search(r'^dynamic\s*=\s*\[\s*"version"\s*\]', text, re.M), (
        "pyproject.toml [project] table must declare "
        '`dynamic = ["version"]` so setuptools reads it from _version.py'
    )
    m = re.search(
        r'\[tool\.setuptools\.dynamic\]\s*\n'
        r'version\s*=\s*\{\s*attr\s*=\s*"([^"]+)"',
        text,
    )
    assert m, (
        "pyproject.toml missing [tool.setuptools.dynamic] version.attr "
        "that points at minxg._version.VERSION"
    )
    assert m.group(1) == "minxg._version.VERSION", (
        f"pyproject version.attr must point at minxg._version.VERSION, "
        f"got {m.group(1)!r}"
    )


def test_init_py_re_exports_ssot():
    """``minxg/__init__.py`` must import ``__version__`` from ``_version``."""
    text = _read(INIT_PY)
    assert "from ._version import" in text, (
        "minxg/__init__.py must `from ._version import VERSION` so "
        "`import minxg; minxg.__version__` returns the SSoT"
    )
    # Belt + braces: the literal must not have its own stale string.
    assert not re.search(r'^VERSION\s*=\s*"', text, re.M), (
        "minxg/__init__.py still declares its own `VERSION = \"…\"` — "
        "remove it, the SSoT lives in minxg/_version.py"
    )


def _readme_drop_line() -> str:
    for line in _read(README).splitlines():
        m = re.match(
            r"^Successfully installed minxg-beta-([0-9]+\.[0-9]+\.[0-9]+)$",
            line.strip(),
        )
        if m:
            return m.group(1)
    return ""


def _changelog_first_section_version() -> str:
    for line in _read(CHANGELOG).splitlines():
        m = re.match(r"^##\s*\[([0-9]+\.[0-9]+\.[0-9]+)", line.strip())
        if m:
            return m.group(1)
    return ""


def _developer_publish_version() -> str:
    """DEVELOPER.md publishing checklist — looks for a `Version: X.Y.Z` line."""
    for line in _read(DEVELOPER).splitlines():
        m = re.match(r"^Version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", line.strip())
        if m:
            return m.group(1)
    return ""


@pytest.mark.parametrize(
    "label,fn",
    [
        ("README.md (pip install line)", _readme_drop_line),
        ("CHANGELOG.md (top section)", _changelog_first_section_version),
        ("DEVELOPER.md (publishing checklist)", _developer_publish_version),
    ],
)
def test_docs_echo_singular_value(label, fn):
    """Doc surfaces must echo ``minxg/_version.py`` — release surfaces drift otherwise."""
    expected = _ssot()
    actual = fn()
    assert actual, f"{label} version not parseable"
    assert actual == expected, (
        f"{label!r} reports {actual!r} but _version.py says {expected!r}; "
        "release drift — re-sync before tagging."
    )
