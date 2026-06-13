"""Config loader — see __init__.py."""
import os, json
from typing import Dict, Any

def load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path): return {}
    with open(path) as f:
        if path.endswith((".yaml", ".yml")):
            try:
                import yaml; return yaml.safe_load(f) or {}
            except ImportError: return {}
        elif path.endswith(".json"):
            return json.load(f)
    return {}

def merge_configs(*configs):
    result = {}
    for c in configs:
        if c: result.update(c)
    return result
