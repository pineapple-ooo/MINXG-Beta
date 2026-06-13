"""



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

SUPPORTED_EXTENSIONS = (".py", ".zip", ".tar.gz", ".tgz")


class ExtensionModule:

    def __init__(self, name: str, description: str, module,
                 priority: int = 50, version: str = "", source: str = "",
                 path: str = ""):
        self.name = name
        self.description = description
        self.module = module
        self.priority = priority
        self.version = version
        self.source = source
        self.path = path

    def register_cli(self, subparsers) -> None:
        fn = getattr(self.module, "register_cli", None)
        if fn:
            try:
                fn(subparsers)
            except Exception as e:
                pass

    def handle(self, args) -> int:
        return self.module.handle_command(args)

    def __repr__(self):
        return f"ExtensionModule({self.name!r}, src={self.source}, pri={self.priority})"





_TEMP_DIRS: List[tempfile.TemporaryDirectory] = []


def _extract_zip(zip_path: Path) -> Optional[Path]:
    try:
        tmp = tempfile.TemporaryDirectory(prefix="minxg_ext_")
        _TEMP_DIRS.append(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp.name)
        return Path(tmp.name)
    except Exception as e:
        return None


def _extract_targz(tar_path: Path) -> Optional[Path]:
    try:
        tmp = tempfile.TemporaryDirectory(prefix="minxg_ext_")
        _TEMP_DIRS.append(tmp)
        with tarfile.open(tar_path, "r:*") as tf:
            tf.extractall(tmp.name)
        return Path(tmp.name)
    except Exception as e:
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
                        if isinstance(target, ast.Name) and target.id == "EXTENSION_NAME":
                            return py_file
        except SyntaxError:
            continue

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





def import_hermes_skill(skill_dir: str) -> Optional[ExtensionModule]:
    """Import a Hermes skill from SKILL.md directory."""
    skill_path = Path(skill_dir)
    if not skill_path.exists():
        return None

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    import yaml
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return None

    name = skill_path.name
    description = ""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1])
                name = meta.get("name", name)
                description = meta.get("description", "")
            except Exception:
                pass

EXTENSION_NAME = "{name}"
EXTENSION_DESCRIPTION = """{description}"""
EXTENSION_VERSION = "imported"
EXTENSION_PRIORITY = 60
EXTENSION_SOURCE = "hermes-import"

def handle_command(args) -> int:
    import subprocess, sys
    skill_dir = str(skill_path)
    skill_py = Path(skill_dir) / "skill.py"
    if skill_py.exists():
        import runpy
        runpy.run_path(str(skill_py), run_name="__main__")
        return 0
    else:
        return 0

def register_cli(subparsers):
    p = subparsers.add_parser("{name}", help="{description}")

def register_hooks(registry):
    @registry.pre_chat
    def inject_skill_context(ctx):
        skill_md = Path(skill_md)
        if skill_md.exists():
            ctx.setdefault("injected_context", []).append(skill_md.read_text(encoding="utf-8"))
        return ctx

    try:
        mod = type(sys)("hermes_import_" + name)
        mod.__dict__.update({
            "Path": Path,
            "print": print,
        })
        exec(compile(wrapper_code, "<hermes_import>", "exec"), mod.__dict__)
    except Exception as e:
        return None

    return ExtensionModule(name, description, mod, priority=60,
                          version="imported", source="imported-hermes",
                          path=str(skill_path))


def import_claude_skill(skill_path: str) -> Optional[ExtensionModule]:
    """Import a Claude Code skill from directory or config file."""
    sp = Path(skill_path)
    if not sp.exists():
        return None

    if sp.is_dir():
        for candidate in [sp / "skill.toml", sp / "skill.json", sp / "definition.toml"]:
            if candidate.exists():
                sp = candidate
                break
        else:
            return None

    name = sp.stem

    if sp.suffix == ".json":
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
            name = data.get("name", name)
            description = data.get("description", description)
        except Exception:
            pass
    elif sp.suffix == ".toml":
        try:
            import tomllib
            data = tomllib.loads(sp.read_text(encoding="utf-8"))
            name = data.get("name", name)
            description = data.get("description", description)
        except ImportError:
            pass
        except Exception:
            pass
EXTENSION_NAME = "{name}"
EXTENSION_DESCRIPTION = "{description}"
EXTENSION_VERSION = "imported"
EXTENSION_PRIORITY = 65
EXTENSION_SOURCE = "claude-import"

def handle_command(args) -> int:
    return 0


def import_codex_tool(tool_path: str) -> Optional[ExtensionModule]:
    """Import a Codex tool definition from JSON file."""
    tp = Path(tool_path)
    if not tp.exists() or tp.suffix != ".json":
        return None

    try:
        data = json.loads(tp.read_text(encoding="utf-8"))
    except Exception:
        return None

    tools = data if isinstance(data, list) else [data]
    name = tp.stem
    return None

import json


def handle_command(args) -> int:
    for t in _tools:
        if isinstance(t, dict) and "function" in t:
            print(f"  - {{t['function']['name']}}")
    return 0

def register_hooks(registry):
    @registry.gateway_middleware
    def inject_tools(request):
        if hasattr(request, "extra_tools"):
            request.extra_tools.extend(_tools)
        return request

    try:
        mod = type(sys)("codex_import_" + name)
        exec(compile(wrapper_code, "<codex_import>", "exec"), mod.__dict__)
    except Exception as e:
        return None

    return ExtensionModule(name, description, mod, priority=70,
                          version="imported", source="imported-codex",
                          path=str(tp))


def run_ext_import(args) -> int:
    framework = getattr(args, "from_framework", "hermes")
    path = args.path

    if framework == "hermes":
        ext = import_hermes_skill(path)
    elif framework == "claude":
        ext = import_claude_skill(path)
    elif framework == "codex":
        ext = import_codex_tool(path)
    else:
        return 1

    if ext is None:
        return 1

    global _cached
    if _cached is None:
        _cached = []
    _cached.append(ext)

    from multiligua_cli.utils import print_success, print_info
    return 0



def _get_extensions_dirs() -> List[Path]:
    base = Path(__file__).parent
    dirs = [
        (base / "builtin", "builtin"),
        (base / "user", "user"),
    ]
    for d, _ in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return [d[0] for d in dirs]


def discover_extensions() -> List[ExtensionModule]:
    seen: set = set()
    loaded: List[ExtensionModule] = []

    for ext_dir in _get_extensions_dirs():
        if not ext_dir.exists():
            continue

        source = ext_dir.name

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
            elif ext_name.endswith(".zip"):
                modules = _load_from_archive(item, f"{source}-zip")
            elif ext_name.endswith(".tar.gz") or ext_name.endswith(".tgz"):
                modules = _load_from_archive(item, f"{source}-targz")
            else:
                continue

            for mod in modules:
                if mod.name in seen:
                    continue
                seen.add(mod.name)
                loaded.append(mod)

    loaded.sort(key=lambda x: (x.priority, x.name))
    return loaded


def _load_py_extension(py_file: Path, source: str) -> List[ExtensionModule]:
    mod = _load_module_from_file(py_file)
    if mod is None:
        return []
    return _validate_and_wrap(mod, source, str(py_file))


def _validate_and_wrap(mod, source: str, path: str) -> List[ExtensionModule]:
    enabled = getattr(mod, "EXTENSION_ENABLED", None)

    adb_ok = getattr(mod, "ADB_AVAILABLE", None)
    root_ok = getattr(mod, "ROOT_AVAILABLE", None)

    if enabled is None:
        if adb_ok is not None:
            enabled = adb_ok
        elif root_ok is not None:
            enabled = root_ok
        else:
            enabled = True

    name = getattr(mod, "EXTENSION_NAME", None)
    desc = getattr(mod, "EXTENSION_DESCRIPTION", "")
    handler = getattr(mod, "handle_command", None)
    priority = getattr(mod, "EXTENSION_PRIORITY", 50)
    version = getattr(mod, "EXTENSION_VERSION", "")

    if not enabled:
        if adb_ok is not None:
            desc += " [INACTIVE: ADB未检测到]"
        elif root_ok is not None:
            desc += " [INACTIVE: 设备未ROOT]"
        else:
            desc += " [INACTIVE: 已禁用]"
    else:
        if adb_ok:
            desc += " [ACTIVE: ADB已连接]"
        elif root_ok:
            desc += " [ACTIVE: ROOT已解锁]"

    if not name or not handler:
        return []

    return [ExtensionModule(name, desc, mod, priority, version, source, path)]


def _load_module_from_file(path: Path):
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
        return None



def reload_extensions() -> List[ExtensionModule]:
    to_pop = [k for k in sys.modules if k.startswith("extensions._dynamic.")]
    for k in to_pop:
        del sys.modules[k]
    global _cached
    _cached = None
    return discover_extensions()


def cleanup_temp_dirs():
    global _TEMP_DIRS
    for td in _TEMP_DIRS:
        try:
            td.cleanup()
        except Exception:
            pass
    _TEMP_DIRS.clear()



_cached: Optional[List[ExtensionModule]] = None


def get_extensions() -> List[ExtensionModule]:
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
    return [
        {
            "name": e.name,
            "description": e.description,
            "version": e.version,
            "source": e.source,
            "priority": e.priority,
            "path": e.path,
        }
        for e in get_extensions()
    ]
