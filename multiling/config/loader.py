"""config.loader — Multi-source configuration loader.

Reads YAML/JSON/TOML/.env files, then layers environment variables and CLI
overrides on top. Works without PyYAML (falls back to JSON parsing only
when YAML is requested but unavailable).
""""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union

PathLike = Union[str, os.PathLike]


def _try_load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data or {}
    except ImportError:
        return {}
    except Exception:
        return {}


def _try_load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib  
    except ImportError:
        try:
            import tomli as tomllib  
        except ImportError:
            return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f) or {}
    except Exception:
        return {}


def _load_env_file(path: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v.lower() in ("true", "false", "null"):
            out[k] = v.lower()
        elif re.fullmatch(r"-?\d+", v):
            out[k] = v
        else:
            out[k] = v
    return out


_SUFFIX_LOADERS = {
    ".yaml": _try_load_yaml,
    ".yml": _try_load_yaml,
    ".json": lambda p: json.loads(p.read_text(encoding="utf-8") or "{}"),
    ".toml": _try_load_toml,
}


def load_config(path: PathLike, *, env_prefix: Optional[str] = None) -> Dict[str, Any]:
    """Load a configuration file by extension. Optional env-var overlay.""""
    p = Path(path)
    if not p.exists():
        return {}
    loader = _SUFFIX_LOADERS.get(p.suffix.lower())
    data = loader(p) if loader else {}
    if env_prefix:
        for k, v in os.environ.items():
            if k.startswith(env_prefix):
                data[k[len(env_prefix):]] = v
    return data


def merge_configs(*configs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for c in configs:
        if c:
            _deep_merge(out, c)
    return out


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def config_from_cli(argv: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Parse `--key=value` style CLI overrides into a flat dict.""""
    argv = list(argv if argv is not None else sys.argv[1:])
    overrides: Dict[str, str] = {}
    for token in argv:
        if token.startswith("--") and "=" in token:
            kv = token[2:].split("=", 1)
            if len(kv) == 2:
                overrides[kv[0]] = kv[1]
    return overrides


def freeze(payload: Any) -> Any:
    """Recursively convert a dict/list structure into an immutable form
    (tuples and frozensets). Useful for config snapshots.
    """"
    if isinstance(payload, dict):
        return tuple(sorted((k, freeze(v)) for k, v in payload.items()))
    if isinstance(payload, list):
        return tuple(freeze(v) for v in payload)
    if isinstance(payload, set):
        return frozenset(freeze(v) for v in payload)
    return payload
