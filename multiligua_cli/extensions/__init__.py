"""
"""
from __future__ import annotations
import os
import sys
import json as _json
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

log = logging.getLogger("extensions.loader")

EXTENSIONS_DIR = Path(__file__).parent.parent.parent / "extensions"


class ExtensionInfo:
    def __init__(self, name: str, path: Path, ext_type: str):
        self.name = name
        self.path = path
        self.ext_type = ext_type  
        self.description = ""
        self.version = "0.1.0"
        self.author = ""
        self.emoji = "📦"
        self.enabled = True
        self.loaded = False
        self.load_error: Optional[str] = None
        self._module = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name, "path": str(self.path), "type": self.ext_type,
            "description": self.description, "version": self.version,
            "author": self.author, "emoji": self.emoji,
            "enabled": self.enabled, "loaded": self.loaded,
        }


class ExtensionLoader:

    def __init__(self):
        self.extensions: Dict[str, ExtensionInfo] = {}
        self._discovery_paths = []

    def add_discovery_path(self, path: str | Path):
        p = Path(path).expanduser().resolve()
        if p.is_dir() and p not in self._discovery_paths:
            self._discovery_paths.append(p)

    def discover(self) -> List[ExtensionInfo]:
        discovered = []

        search_paths = list(self._discovery_paths)
        default = EXTENSIONS_DIR
        if default.is_dir() and default not in search_paths:
            search_paths.append(default)

        for search_dir in search_paths:
            if not search_dir.is_dir():
                continue
            for item in sorted(search_dir.iterdir()):
                info = self._inspect(item)
                if info:
                    if info.name not in self.extensions:
                        self.extensions[info.name] = info
                        discovered.append(info)
                    else:
                        pass

        for ext in self.extensions.values():
            if ext.enabled and not ext.loaded:
                self._load_extension(ext)

        return discovered

    def _inspect(self, path: Path) -> Optional[ExtensionInfo]:
        name = path.stem

        if path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
            info = ExtensionInfo(name, path, "py")
            self._read_py_metadata(info, path)
            return info

        if path.is_dir() and not path.name.startswith("_") and not path.name.startswith("."):
            init = path / "__init__.py"
            if init.is_file():
                info = ExtensionInfo(name, path, "dir")
                self._read_py_metadata(info, init)
                return info
            main = path / "main.py"
            if main.is_file():
                info = ExtensionInfo(name, path, "dir")
                self._read_py_metadata(info, main)
                return info

        if path.is_file() and path.suffix == ".zip":
            import zipfile
            try:
                with zipfile.ZipFile(path) as zf:
                    names = zf.namelist()
                    has_py = any(n.endswith(".py") for n in names)
                    has_json = any(n.endswith("extension.json") for n in names)
                    if has_py:
                        info = ExtensionInfo(name, path, "zip")
                        if has_json:
                            meta = _json.loads(zf.read(next(n for n in names if n.endswith("extension.json"))))
                            info.description = meta.get("description", "")
                            info.version = meta.get("version", "0.1.0")
                            info.author = meta.get("author", "")
                            info.emoji = meta.get("emoji", "📦")
                        return info
            except Exception:
                pass

        if path.is_file() and path.suffix == ".md":
            info = ExtensionInfo(name, path, "md")
            try:
                content = path.read_text(encoding="utf-8")[:500]
                for line in content.split("\n"):
                    if line.startswith("# "):
                        info.description = line[2:].strip()
                        break
            except Exception:
                pass
            info.emoji = "📄"
            return info

        return None

    def _read_py_metadata(self, info: ExtensionInfo, py_path: Path):
        try:
            content = py_path.read_text(encoding="utf-8")
            import ast
            tree = ast.parse(content)
            if (isinstance(tree.body[0], ast.Expr) and
                    isinstance(tree.body[0].value, (ast.Constant, ast.Str))):
                doc = ast.get_docstring(tree)
                if doc:
                    first_line = doc.strip().split("\n")[0]
                    info.description = first_line[:120]

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            val = node.value
                            if target.id == "__version__" and isinstance(val, (ast.Constant, ast.Str)):
                                info.version = val.value if hasattr(val, 'value') else val.s
                            elif target.id == "__author__" and isinstance(val, (ast.Constant, ast.Str)):
                                info.author = val.value if hasattr(val, 'value') else val.s
                            elif target.id == "__emoji__" and isinstance(val, (ast.Constant, ast.Str)):
                                info.emoji = val.value if hasattr(val, 'value') else val.s
        except Exception as e:
            pass

    def _load_extension(self, ext: ExtensionInfo):
        if ext.ext_type == "py":
            try:
                spec = importlib.util.spec_from_file_location(
                    f"ext_{ext.name}", ext.path
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"ext_{ext.name}"] = module
                spec.loader.exec_module(module)
                ext._module = module
                ext.loaded = True
            except Exception as e:
                ext.load_error = str(e)

        elif ext.ext_type == "dir":
            try:
                init = ext.path / "__init__.py"
                main = ext.path / "main.py"
                py_file = init if init.is_file() else main
                spec = importlib.util.spec_from_file_location(
                    f"ext_{ext.name}", py_file
                )
                module = importlib.util.module_from_spec(spec)
                if str(ext.path) not in sys.path:
                    sys.path.insert(0, str(ext.path))
                spec.loader.exec_module(module)
                ext._module = module
                ext.loaded = True
            except Exception as e:
                ext.load_error = str(e)

        elif ext.ext_type == "zip":
            try:
                import zipfile, tempfile, shutil
                tmp = Path(tempfile.mkdtemp(prefix=f"ext_{ext.name}_"))
                with zipfile.ZipFile(ext.path) as zf:
                    zf.extractall(tmp)
                if str(tmp) not in sys.path:
                    sys.path.insert(0, str(tmp))
                for candidate in ["main", "__init__", ext.name]:
                    py = tmp / f"{candidate}.py"
                    if py.is_file():
                        spec = importlib.util.spec_from_file_location(f"ext_{ext.name}", py)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        ext._module = module
                        ext.loaded = True
                        break
                if not ext.loaded:
                    ext.load_error = "no main.py or __init__.py found in zip"
            except Exception as e:
                ext.load_error = str(e)

        elif ext.ext_type == "md":
                    pass

    def list_all(self) -> List[ExtensionInfo]:
        return list(self.extensions.values())

    def get(self, name: str) -> Optional[ExtensionInfo]:
        return self.extensions.get(name)

    def enable(self, name: str):
        ext = self.extensions.get(name)
        if ext and not ext.enabled:
            ext.enabled = True
            if not ext.loaded:
                self._load_extension(ext)

    def disable(self, name: str):
        ext = self.extensions.get(name)
        if ext:
            ext.enabled = False

    def remove(self, name: str):
        if name in self.extensions:
            del self.extensions[name]

    def install_from_path(self, src: str | Path) -> Optional[ExtensionInfo]:
        src_path = Path(src).expanduser().resolve()
        if not src_path.exists():
            return None

        EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)

        if src_path.is_file():
            import shutil
            dest = EXTENSIONS_DIR / src_path.name
            shutil.copy2(src_path, dest)
            info = self._inspect(dest)
        elif src_path.is_dir():
            import shutil
            dest = EXTENSIONS_DIR / src_path.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src_path, dest)
            info = self._inspect(dest)
        else:
            return None

        if info:
            self.extensions[info.name] = info
            if info.enabled:
                self._load_extension(info)
        return info

    def install_sample(self) -> ExtensionInfo:
        EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
        dest = EXTENSIONS_DIR / "hello_world.py"
        content = '''"""
"""
__version__ = "0.1.0"
__author__ = "MINXG Community"
__emoji__ = "👋"

def register(cli):

def greet(name: str = "World") -> str:
    return f"Hello, {name}! This is MINXG extension speaking. 🌍"
'''
        dest.write_text(content, encoding="utf-8")
        info = self._inspect(dest)
        if info:
            self.extensions[info.name] = info
            self._load_extension(info)
        return info


_loader: Optional[ExtensionLoader] = None


def get_loader() -> ExtensionLoader:
    global _loader
    if _loader is None:
        _loader = ExtensionLoader()
    return _loader






def register_cli_extensions(subparsers) -> Dict[str, Any]:
    return {}


def list_extensions() -> List[Dict[str, Any]]:
    loader = get_loader()
    loader.discover()
    return [ext.to_dict() for ext in loader.extensions.values()]


def dispatch_extension(ext_map: Dict, cmd: str, args) -> int:
    handler = ext_map.get(cmd)
    if handler:
        return handler(args)
    return 0
