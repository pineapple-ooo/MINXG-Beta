"""Load and expose project config from config/minxg.yaml.""""
import os
from pathlib import Path
from typing import Any, Dict

_config: Dict[str, Any] = {}

def load_config() -> Dict[str, Any]:
    """Load config/minxg.yaml. Returns dict.""""
    global _config
    if _config:
        return _config
    try:
        import yaml
    except ImportError:
        return _config
    config_path = Path(__file__).parent.parent / "config" / "minxg.yaml"
    if not config_path.exists():
        return _config
    with open(config_path) as f:
        _config = yaml.safe_load(f) or {}
    return _config

def get(key: str, default: Any = None) -> Any:
    """Get a config value by dot path. e.g. get('project.version').""""
    cfg = load_config()
    parts = key.split(".")
    cur = cfg
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

CONFIG = load_config()
