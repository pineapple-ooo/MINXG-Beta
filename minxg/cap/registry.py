"""Default-registry helpers backed by the package's own source tree."""
from __future__ import annotations
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manifest import CapManifest


_default: Optional["CapManifest"] = None


def _resolve_root() -> Path:
    """Locate the repository's Python source root."""
    here = Path(__file__).resolve()
    candidate = here.parent.parent
    if (candidate / "minxg").is_dir() or (candidate / "multiling").is_dir():
        return candidate / "minxg"
    return candidate


def get_manifest(*, root_override: Optional[Path] = None) -> "CapManifest":
    global _default
    if _default is not None and root_override is None:
        return _default
    from .manifest import CapManifest
    from .scanner import scan_tree
    manifest = CapManifest()
    root = root_override or _resolve_root()
    for record in scan_tree(root):
        manifest.add(record)
    if root_override is None:
        _default = manifest
    return manifest


def reset_manifest() -> "CapManifest":
    global _default
    _default = None
    return get_manifest()


def reindex() -> "CapManifest":
    return reset_manifest()
