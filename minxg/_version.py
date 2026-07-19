"""minxg._version — single source of truth for the project version.

WHY a dedicated file?
---------------------
The codebase touches the version number in three logical places:

1. ``pyproject.toml``  — what gets uploaded to PyPI
2. ``minxg/__init__.py``  — what ``import minxg; minxg.__version__`` shows
3. ``CHANGELOG.md`` / banner strings  — what humans see/read

Before this file existed you'd have to remember to bump all three in
lockstep and any miss would silently desync them. Now you change ONE line
in this file and three thin re-exporters pull from it:

* ``pyproject.toml`` reads ``minxg._version.VERSION`` via setuptools
  ``dynamic`` (``[project] dynamic = ["version"]``)
* ``minxg/__init__.py`` does ``from ._version import VERSION as __version__``
* ``version_tools/version_worker`` (and friends) call ``get_version()``

That is the entire contract. If you need to bump the release, just edit
``VERSION`` below and run ``python -m minxg._version`` to confirm the
new value, then commit. Everything else propagates automatically.
"""
from __future__ import annotations

import re
import sys
from typing import Tuple

# ---- bump rules --------------------------------------------------------
#   Major breaking changes → bump major
#   Backwards-compatible features  → bump minor
#   Bug fixes / wording      → bump patch
VERSION = "0.18.5"


def parse(vv: str = VERSION) -> Tuple[int, int, int]:
    """Parse ``X.Y.Z`` (or ``X.Y.Z+local``, ``X.Y.Za1``) into a 3-tuple.

    Accepts any leading digits before the first ``.`` so pre-1.0 builds
    (``0.13.1``, ``0.13.1a2``, ``0.13.1+termux``) all work.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", vv)
    if not m:
        raise ValueError(f"Unrecognised version: {vv!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


_maj, _min, _pat = parse()


def get_version() -> str:
    """Public accessor — returns the declared ``VERSION`` constant."""
    return VERSION


def banner() -> str:
    """Return ``{major}.{minor}`` — for compact one-line UI banners."""
    return f"{_maj}.{_min}"


if __name__ == "__main__":  # pragma: no cover
    sys.stdout.write(f"{VERSION}\n{banner()}\n{parse()}\n")
