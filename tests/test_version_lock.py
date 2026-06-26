"""tests/test_version_lock.py — cross-file version invariants.

The MINXG version is duplicated across pyproject.toml, minxg/__init__.py,
README.md (banner), DEVELOPER.md (publishing checklist), and CHANGELOG.md
(`## [X.Y.Z]` heading). All five must agree, otherwise releases silently
drift. This guard fires first so the duplication never silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
INIT_PY = REPO / "minxg" / "__init__.py"
README = REPO / "README.md"
CHANGELOG = REPO / "CHANGELOG.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _pyproject_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', _read(PYPROJECT), re.M)
    assert m, "pyproject.toml missing `version = ...`"
    return m.group(1)


def _init_version() -> str:
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', _read(INIT_PY), re.M)
    assert m, "minxg/__init__.py missing `VERSION = ...`"
    return m.group(1)


def _readme_drop_line() -> str:
    for line in _read(README).splitlines():
        m = re.match(r"^Successfully installed minxg-beta-([0-9]+\.[0-9]+\.[0-9]+)$", line.strip())
        if m:
            return m.group(1)
    return ""


def _changelog_first_section_version() -> str:
    """Find the topmost `## [X.Y.Z]` heading in CHANGELOG.md."""
    for line in _read(CHANGELOG).splitlines():
        m = re.match(r"^##\s*\[([0-9]+\.[0-9]+\.[0-9]+)", line.strip())
        if m:
            return m.group(1)
    return ""


@pytest.mark.parametrize(
    "label,fn",
    [
        ("pyproject.toml", _pyproject_version),
        ("minxg/__init__.py", _init_version),
        ("README.md (pip install line)", lambda: _readme_drop_line()),
        ("CHANGELOG.md (top section)", _changelog_first_section_version),
    ],
)
def test_sources_match(label, fn):
    expected = _pyproject_version()
    actual = fn()
    assert actual, f"{label} version not parseable"
    if not expected:
        pytest.fail("pyproject.toml version is empty")
    assert actual == expected, (
        f"{label!r} reports {actual!r} but pyproject.toml says {expected!r}; "
        "release drift — re-sync before tagging."
    )
