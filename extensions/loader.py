"""
extensions/loader.py — Discover and load MINXG extension modules.

Two extension roots:

  - extensions/builtin/    — ships inside the package; builtins are kept
                             EXTENSION_ENABLED = False at the source so they
                             never auto-attach. Users opt in explicitly with
                             `minxg ext add <slug>`, which sets their state
                             to True in extensions/user/<name>.state.
  - extensions/user/       — drop-in directory; everything goes through
                             the same validator and is opt-in by default
                             unless the user-controlled state file says
                             otherwise.

Discovery sequence:
  1. Walk both roots, prefer builtin if a slug is duplicated.
  2. Each candidate is loaded with importlib.util.spec_from_file_location
     under extensions._dynamic.<slug>; clearing the sys.modules entry on
     reload prevents stale closures.
  3. _validate_and_wrap enforces the contract: EXTENSION_NAME, EXTENSION_DESCRIPTION,
     handle_command. EXTENSION_ENABLED defaults to False unless a state file
     in extensions/user/ explicitly marks it enabled.

State files live at extensions/user/<ext-name>.state with a single line
JSON object like {"enabled": true, "version": "1.0.1"}. Lightweight by
design — we are not building a package manager.

Heavy auto-detect ladders (ADB_AVAILABLE / ROOT_AVAILABLE) are NOT consulted.
Each builtin's `handle_command` re-probes (cheap, only when invoked) and
returns 1 with a hint if the dependency is missing. This avoids the
"small workshop framed as a kitchen sink" trap.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import os
import shutil
import sys
import tempfile
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("extensions")


REQUIRED_ATTRS = ["EXTENSION_NAME", "EXTENSION_DESCRIPTION", "handle_command"]
OPTIONAL_ATTRS = ["register_cli", "register_hooks"]
SUPPORTED_EXTENSIONS = (".py", ".zip", ".tar.gz", ".tgz", ".json")

# JSON manifest file names that an extension may carry alongside its
# Python sources. The contents are used as metadata: ``name``, ``version``
# and ``description`` flow through to ``list_extensions()`` even when the
# underlying module has the legacy EXTENSION_NAME etc. constants.
# This is the 0.14.0 "extension interface strengthening" change — the
# contract is now driven by a readable JSON file rather than scattered
# attribute strings.
_MANIFEST_CANDIDATES = ("manifest.json", "minxg.json", "extension.json")


class ExtensionModule:
    """Wraps an extension module with metadata for the package_cli surface."""

    def __init__(self, name: str, description: str, module,
                 priority: int = 50, version: str = "", source: str = "",
                 path: str = "", enabled: bool = False):
        self.name = name
        self.description = description
        self.module = module
        self.priority = priority
        self.version = version
        self.source = source
        self.path = path
        self.enabled = enabled

    def register_cli(self, subparsers) -> None:
        fn = getattr(self.module, "register_cli", None)
        if fn:
            try:
                fn(subparsers)
            except Exception as e:
                logger.warning("register_cli failed for %s: %s", self.name, e)

    def handle(self, args) -> int:
        return self.module.handle_command(args)

    def __repr__(self) -> str:
        return (f"ExtensionModule({self.name!r}, src={self.source}, "
                f"pri={self.priority}, enabled={self.enabled})")


_TEMP_DIRS: List[tempfile.TemporaryDirectory] = []

_cached: Optional[List[ExtensionModule]] = None


def _user_state_dir() -> Path:
    """Where per-extension opt-in state files live."""
    return Path(__file__).parent / "user"


def _read_state(ext_name: str) -> Dict[str, Any]:
    """Read extensions/user/<ext_name>.state — empty dict if missing."""
    p = _user_state_dir() / f"{ext_name}.state"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(ext_name: str, **fields: Any) -> None:
    """Persist a state file under extensions/user/."""
    user_dir = _user_state_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    cur = _read_state(ext_name)
    cur.update(fields)
    (user_dir / f"{ext_name}.state").write_text(
        json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _default_enabled(mod, name: str) -> bool:
    """Look up `enabled` from:
       (1) the user state file at extensions/user/<name>.state,
       (2) the module-level EXTENSION_ENABLED attribute,
       (3) False for builtins, True for user extensions.
    """
    state = _read_state(name)
    if "enabled" in state:
        return bool(state["enabled"])
    return bool(getattr(mod, "EXTENSION_ENABLED", False))


def set_extension_enabled(name: str, enabled: bool) -> None:
    """Persist opt-in state for an extension."""
    _write_state(name, enabled=enabled)
    if _cached is not None:
        for ext in _cached:
            if ext.name == name:
                ext.enabled = enabled
                return


def _read_manifest(ext_root: Path) -> Dict[str, Any]:
    """Look for ``manifest.json`` / ``minxg.json`` / ``extension.json``
    inside ``ext_root`` and return its parsed contents.

    The manifest is the 0.14.0 way extensions declare name/version/
    description to MINXG: it is read ONLY for metadata, the executable
    surface still has to be a Python module with ``handle_command``. A
    missing or malformed manifest is *not* an error — it just returns
    ``{}`` and lets the module-level attributes take over.
    """
    if not ext_root.exists() or not ext_root.is_dir():
        return {}
    for name in _MANIFEST_CANDIDATES:
        candidate = ext_root / name
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("manifest %s unreadable: %s", candidate, exc)
            return {}
        if isinstance(payload, dict):
            return payload
    return {}


def _extract_zip(zip_path: Path) -> Optional[Path]:
    try:
        tmp = tempfile.TemporaryDirectory(prefix="minxg_ext_")
        _TEMP_DIRS.append(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp.name)
        return Path(tmp.name)
    except Exception as e:
        logger.warning("zip extract failed for %s: %s", zip_path, e)
        return None


def _extract_targz(tar_path: Path) -> Optional[Path]:
    try:
        tmp = tempfile.TemporaryDirectory(prefix="minxg_ext_")
        _TEMP_DIRS.append(tmp)
        with tarfile.open(tar_path, "r:*") as tf:
            tf.extractall(tmp.name)
        return Path(tmp.name)
    except Exception as e:
        logger.warning("tar extract failed for %s: %s", tar_path, e)
        return None


def _find_main_py(extract_dir: Path) -> Optional[Path]:
    """Find the main entry point in an extracted extension directory."""
    init_py = extract_dir / "__init__.py"
    if init_py.exists():
        return init_py

    sibling = extract_dir / f"{extract_dir.name}.py"
    if sibling.exists():
        return sibling

    import ast
    for py_file in sorted(extract_dir.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (isinstance(target, ast.Name)
                                and target.id == "EXTENSION_NAME"):
                            return py_file
        except SyntaxError:
            continue
    return None


def _load_module_from_file(path: Path):
    """importlib-based loader. Caches under extensions._dynamic.<slug>."""
    mod_name = f"extensions._dynamic.{path.stem}"
    try:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        sys.modules.pop(mod_name, None)
        logger.warning("module load failed for %s: %s", path, e)
        return None


def _load_from_archive(archive_path: Path, source: str) -> List[ExtensionModule]:
    ext = archive_path.suffix.lower()
    if archive_path.name.endswith(".tar.gz"):
        ext = ".tar.gz"
    elif archive_path.name.endswith(".tgz"):
        ext = ".tgz"
    if ext == ".zip":
        extract_dir = _extract_zip(archive_path)
    elif ext in (".tar.gz", ".tgz"):
        extract_dir = _extract_targz(archive_path)
    else:
        return []
    if extract_dir is None:
        return []
    main_py = _find_main_py(extract_dir)
    if main_py is None:
        return []
    parent = str(main_py.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    mod = _load_module_from_file(main_py)
    if mod is None:
        return []
    return _validate_and_wrap(mod, source, str(archive_path))


def _load_json_manifest_extension(json_file: Path,
                                   source: str) -> List[ExtensionModule]:
    """Recognise a standalone JSON file as an extension entry.

    This is the 0.14.0 "drop-in manifest" path — packages that travel
    with only a JSON file (e.g. drop-in metadata-only stubs, or
    declarations of vendor plugins that ship elsewhere) are picked up
    here. File name MUST end in ``.manifest.json`` / ``.minxg.json`` /
    ``.extension.json`` to keep the heuristic narrow.
    """
    if json_file.suffix != ".json":
        return []
    stem = json_file.name.lower()
    if not any(stem.endswith(s) for s in (
        ".manifest.json", ".minxg.json", ".extension.json",
    )):
        return []
    try:
        payload = json.loads(json_file.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("json ext %s unreadable: %s", json_file, exc)
        return []
    if not isinstance(payload, dict):
        return []
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return []
    desc = str(payload.get("description", ""))
    version = str(payload.get("version", "0.0.0"))
    priority = int(payload.get("priority", 50))

    class _JsonOnlyShim:
        """Minimal stand-in so ``handle`` does not blow up on no-handler extensions."""
        def __init__(self, payload_):
            self._payload = payload_
        def handle_command(self, args):  # noqa: ANN001
            sys.stderr.write(
                f"[minxg.ext] {name} is a manifest-only entry — "
                f"no executable handler is registered.\n"
            )
            return 1

    shim = _JsonOnlyShim(payload)
    enabled = bool(_read_state(name).get("enabled", False))
    return [ExtensionModule(name, desc, shim, priority, version,
                            source, str(json_file), enabled)]


def _load_py_extension(py_file: Path, source: str) -> List[ExtensionModule]:
    mod = _load_module_from_file(py_file)
    if mod is None:
        return []
    manifest = _read_manifest(_ext_root_for(py_file))
    return _validate_and_wrap(mod, source, str(py_file),
                              manifest=manifest)


def _ext_root_for(py_file: Path) -> Path:
    """The directory the manifest is expected to live in.

    For a flat ``xyz.py`` extension, that's just the parent of the file.
    For a packaged ``mypkg/__init__.py``, it's the package directory.
    """
    if py_file.name == "__init__.py":
        return py_file.parent
    return py_file.parent


def _validate_and_wrap(mod, source: str, path: str,
                       manifest: Optional[Dict[str, Any]] = None,
                       name_override: Optional[str] = None) -> List[ExtensionModule]:
    """Wrap `mod` into an ExtensionModule if it satisfies the contract.

    Anti auto-detect: do NOT consult ADB_AVAILABLE / ROOT_AVAILABLE.
    Each extension is responsible for probing its own dependencies inside
    `handle_command` and reporting back honestly. The runner stays free
    of plugin-curated ladders.

    Manifest precedence (0.14.0 — JSON-driven extension contract):
      * If the extension lives next to a ``manifest.json`` whose ``name``
        is present, it wins.
      * The Python ``EXTENSION_NAME``/``EXTENSION_VERSION``/etc. are
        kept as fallback names.

    A ``name_override`` arg lets the caller (e.g. flat ``my_ext.py```
    becoming manifest ``my-ext``) align the metadata name with the
    file the user dropped in.
    """
    module_name = getattr(mod, "EXTENSION_NAME", None)
    manifest_name = (manifest or {}).get("name") if manifest else None
    name = (
        (name_override or "").strip()
        or (str(manifest_name).strip() if manifest_name else "")
        or (module_name.strip() if isinstance(module_name, str) else "")
    )
    if not isinstance(name, str) or not name:
        logger.debug("extension at %s missing name (manifest + module); skipped", path)
        return []
    desc = (
        (manifest or {}).get("description")
        if manifest and (manifest or {}).get("description") is not None
        else getattr(mod, "EXTENSION_DESCRIPTION", "")
    )
    handler = getattr(mod, "handle_command", None)
    if not callable(handler):
        logger.debug("extension %s missing handle_command; skipped", name)
        return []
    priority = int(getattr(mod, "EXTENSION_PRIORITY", 50))
    version = str(
        (manifest or {}).get("version")
        if manifest and (manifest or {}).get("version") is not None
        else getattr(mod, "EXTENSION_VERSION", "")
    )
    enabled = _default_enabled(mod, name)
    return [ExtensionModule(
        name, str(desc or ""), mod, priority, version, source,
        path, enabled,
    )]


def _get_extensions_dirs() -> List[tuple]:
    base = Path(__file__).parent
    dirs = [
        (base / "builtin", "builtin"),
        (base / "user", "user"),
    ]
    for d, _ in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def discover_extensions() -> List[ExtensionModule]:
    """Walk builtin/ then user/, return every loadable extension."""
    seen: set = set()
    loaded: List[ExtensionModule] = []
    for ext_dir, source in _get_extensions_dirs():
        if not ext_dir.exists():
            continue
        items = sorted(ext_dir.iterdir(), key=lambda x: x.name)
        for item in items:
            if item.name.startswith("_") or item.name.startswith("."):
                continue
            ext_name = item.name.lower()
            if item.is_dir():
                init_py = item / "__init__.py"
                if init_py.exists():
                    modules = _load_py_extension(init_py, source)
                else:
                    found = list(item.rglob("__init__.py"))
                    if found:
                        modules = _load_py_extension(found[0], source)
                    else:
                        continue
            elif item.suffix == ".py":
                modules = _load_py_extension(item, source)
            elif item.suffix == ".json":
                modules = _load_json_manifest_extension(item, source) or []
                if not modules:
                    # An unrelated JSON file (e.g. theme.json) — skip.
                    continue
            elif ext_name.endswith(".zip"):
                modules = _load_from_archive(item, f"{source}-zip")
            elif ext_name.endswith(".tar.gz") or ext_name.endswith(".tgz"):
                modules = _load_from_archive(item, f"{source}-targz")
            else:
                continue
            for ext in modules:
                if ext.name in seen:
                    continue
                seen.add(ext.name)
                loaded.append(ext)
    loaded.sort(key=lambda x: (x.priority, x.name))
    return loaded


def reload_extensions() -> List[ExtensionModule]:
    """Force a fresh discovery. Used by `minxg ext add/remove`."""
    to_pop = [k for k in sys.modules if k.startswith("extensions._dynamic.")]
    for k in to_pop:
        del sys.modules[k]
    global _cached
    _cached = None
    return discover_extensions()


def rescan_all() -> int:
    """Alias for ``reload_extensions`` that returns a count.

    Used by the experimental ``minxg ext-reload`` verb.
    """
    return len(reload_extensions())


__all__ = [
    "ExtensionModule",
    "discover_extensions",
    "reload_extensions",
    "rescan_all",
    "get_extensions",
    "get_extension",
    "list_extensions",
    "set_extension_enabled",
    "cleanup_temp_dirs",
]


def cleanup_temp_dirs() -> None:
    """Drop any zip-extract tmp dirs we kept alive."""
    global _TEMP_DIRS
    for td in _TEMP_DIRS:
        try:
            td.cleanup()
        except Exception:
            pass
    _TEMP_DIRS.clear()


def get_extensions() -> List[ExtensionModule]:
    """Cached discovery; first call walks the disk, later calls hit memory."""
    global _cached
    if _cached is None:
        _cached = discover_extensions()
    return _cached


def get_extension(name: str) -> Optional[ExtensionModule]:
    for ext in get_extensions():
        if ext.name == name:
            return ext
    return None


def list_extensions() -> List[dict]:
    """Return a JSON-friendly list of all installed extensions."""
    return [
        {
            "name": e.name,
            "description": e.description,
            "version": e.version,
            "source": e.source,
            "priority": e.priority,
            "path": e.path,
            "enabled": e.enabled,
        }
        for e in get_extensions()
    ]
