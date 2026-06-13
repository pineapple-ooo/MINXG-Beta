"""
config.py - Configuration Management System

Provides:
  - Config: Type-safe configuration with validation
  - ConfigLoader: Load from YAML/JSON/env/CLI
  - ConfigSection: Nested configuration sections
  - ConfigWatcher: Hot-reload configuration on file change
  - Validators: Built-in validation rules
"""

import asyncio
import copy
import hashlib
import json
import os
import pickle
import re
import secrets
import threading
import time
from typing import (
    Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Type,
    Union,
)
from dataclasses import dataclass, field
from collections import OrderedDict
from pathlib import Path


class ValidationError(Exception):
    """Raised when a config value fails validation"""

    def __init__(self, key: str, value: Any, rule: str, message: str = ""):
        self.key = key
        self.value = value
        self.rule = rule
        self.message = message or "Validation failed for '{}': {} (rule: {})".format(key, value, rule)
        super().__init__(self.message)


class Validator:
    """Built-in validation rules"""

    @staticmethod
    def required(value: Any) -> Any:
        if value is None:
            raise ValueError("Value is required")
        return value

    @staticmethod
    def string(value: Any, min_len: int = 0, max_len: int = None) -> str:
        s = str(value)
        if len(s) < min_len:
            raise ValueError("String too short (min {})".format(min_len))
        if max_len and len(s) > max_len:
            raise ValueError("String too long (max {})".format(max_len))
        return s

    @staticmethod
    def integer(value: Any, min_val: int = None, max_val: int = None) -> int:
        i = int(value)
        if min_val is not None and i < min_val:
            raise ValueError("Value {} below minimum {}".format(i, min_val))
        if max_val is not None and i > max_val:
            raise ValueError("Value {} above maximum {}".format(i, max_val))
        return i

    @staticmethod
    def float(value: Any, min_val: float = None, max_val: float = None) -> float:
        f = float(value)
        if min_val is not None and f < min_val:
            raise ValueError("Value {} below minimum {}".format(f, min_val))
        if max_val is not None and f > max_val:
            raise ValueError("Value {} above maximum {}".format(f, max_val))
        return f

    @staticmethod
    def boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "1", "on"):
                return True
            if value.lower() in ("false", "no", "0", "off"):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError("Cannot convert {} to boolean".format(type(value)))

    @staticmethod
    def choice(value: Any, allowed: Sequence) -> Any:
        if value not in allowed:
            raise ValueError("Value '{}' not in allowed: {}".format(value, allowed))
        return value

    @staticmethod
    def list_of(value: Any, item_type: type = str) -> list:
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [item_type(v) for v in value]

    @staticmethod
    def regex(value: str, pattern: str) -> str:
        if not re.match(pattern, value):
            raise ValueError("Value '{}' does not match pattern '{}'".format(value, pattern))
        return value

    @staticmethod
    def path(value: Any, must_exist: bool = False) -> str:
        p = str(value)
        if must_exist and not os.path.exists(p):
            raise ValueError("Path '{}' does not exist".format(p))
        return p

    @staticmethod
    def enum(*values) -> Callable:
        def checker(value):
            if value not in values:
                raise ValueError("Value must be one of: {}".format(values))
            return value
        return checker


@dataclass
class ConfigField:
    """A single configuration field definition"""
    name: str
    default: Any = None
    field_type: type = str
    required: bool = False
    validator: Optional[Callable] = None
    description: str = ""
    sensitive: bool = False  # Marks field as secret (redact on display)


class ConfigSection:
    """A nested configuration section with typed fields"""

    def __init__(self, name: str, parent: "ConfigSection" = None):
        self.name = name
        self.parent = parent
        self._fields: Dict[str, ConfigField] = OrderedDict()
        self._values: Dict[str, Any] = {}
        self._children: Dict[str, ConfigSection] = {}
        self._validators: Dict[str, List[Callable]] = {}

    def add_field(self, name: str, default: Any = None,
                  field_type: type = str, required: bool = False,
                  validator: Callable = None, description: str = "",
                  sensitive: bool = False) -> "ConfigSection":
        """Add a typed field to this section"""
        self._fields[name] = ConfigField(
            name=name, default=default, field_type=field_type,
            required=required, validator=validator,
            description=description, sensitive=sensitive,
        )
        if default is not None:
            self._values[name] = default
        return self

    def add_child(self, name: str) -> "ConfigSection":
        """Add a nested sub-section"""
        child = ConfigSection(name, parent=self)
        self._children[name] = child
        return child

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._values:
            return self._values[name]
        if name in self._children:
            return self._children[name]
        if name in self._fields:
            return self._fields[name].default
        raise AttributeError("No config field '{}' in section '{}'".format(name, self.name))

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_") or name in ("name", "parent", "_fields", "_values",
                                             "_children", "_validators"):
            super().__setattr__(name, value)
            return
        self.set(name, value)

    def set(self, name: str, value: Any, validate: bool = True):
        """Set a config value with optional validation"""
        if name in self._fields:
            field_def = self._fields[name]
            # Type coercion
            try:
                if field_def.field_type is not Any:
                    value = field_def.field_type(value)
            except (ValueError, TypeError) as e:
                raise ValidationError(name, value, "type", str(e))
            # Custom validator
            if validate and field_def.validator:
                value = field_def.validator(value)
            # Run registered validators
            if validate and name in self._validators:
                for vfn in self._validators[name]:
                    vfn(value)
        self._values[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get a config value"""
        return self._values.get(name, default)

    def has(self, name: str) -> bool:
        return name in self._values

    def path(self, sep: str = ".") -> str:
        """Get full dotted path of this section"""
        if self.parent:
            return self.parent.path(sep) + sep + self.name
        return self.name

    def flatten(self, prefix: str = "", include_sensitive: bool = False) -> Dict:
        """Flatten to a simple dict"""
        result = {}
        for name, val in self._values.items():
            key = prefix + name if prefix else name
            field_def = self._fields.get(name)
            if field_def and field_def.sensitive and not include_sensitive:
                result[key] = "[REDACTED]"
            else:
                result[key] = val
        for name, child in self._children.items():
            child_prefix = prefix + name + "."
            result.update(child.flatten(child_prefix, include_sensitive))
        return result

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to nested dict"""
        result = {}
        for name, val in self._values.items():
            field_def = self._fields.get(name)
            if field_def and field_def.sensitive and not include_sensitive:
                result[name] = "[REDACTED]"
            else:
                result[name] = val
        for name, child in self._children.items():
            result[name] = child.to_dict(include_sensitive)
        return result

    def validate(self) -> List[ValidationError]:
        """Validate all fields, returns list of errors"""
        errors = []
        for name, field_def in self._fields.items():
            if field_def.required and name not in self._values:
                errors.append(ValidationError(
                    name, None, "required",
                    "Required field '{}' is missing".format(name),
                ))
        for child in self._children.values():
            errors.extend(child.validate())
        return errors

    def keys(self) -> Iterator[str]:
        return iter(self._values.keys())

    def items(self) -> Iterator[Tuple[str, Any]]:
        return iter(self._values.items())


class Config:
    """
    Main configuration container

    Usage:
        config = Config()
        config.load_yaml("config.yaml")
        config.db.host  # Access nested value
        config.set("debug", True)
    """

    def __init__(self, name: str = "app"):
        self.name = name
        self._root = ConfigSection("root")
        self._sources: List[str] = []
        self._env_prefix: str = ""
        self._version: int = 1
        self._checksum: str = ""
        self._lock = threading.Lock()

    @property
    def root(self) -> ConfigSection:
        return self._root

    def section(self, name: str, create: bool = True) -> ConfigSection:
        """Get or create a configuration section"""
        if name in self._root._children:
            return self._root._children[name]
        if create:
            return self._root.add_child(name)
        raise KeyError("Section '{}' not found".format(name))

    def get(self, path: str, default: Any = None) -> Any:
        """Get value by dotted path (e.g., 'database.host')"""
        parts = path.split(".")
        current = self._root
        for part in parts[:-1]:
            if part in current._children:
                current = current._children[part]
            else:
                return default
        return current._values.get(parts[-1], default)

    def set(self, path: str, value: Any, validate: bool = True):
        """Set value by dotted path"""
        with self._lock:
            parts = path.split(".")
            current = self._root
            for part in parts[:-1]:
                if part not in current._children:
                    current = current.add_child(part)
                else:
                    current = current._children[part]
            current.set(parts[-1], value, validate=validate)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._root._children:
            return self._root._children[name]
        if name in self._root._values:
            return self._root._values[name]
        raise AttributeError("No config section or field '{}'".format(name))

    def load_dict(self, data: Dict, prefix: str = "", merge: bool = True):
        """Load config from a flat or nested dict"""
        self._load_dict_recursive(self._root, data, prefix, merge)

    def _load_dict_recursive(self, section: ConfigSection, data: Dict,
                             prefix: str, merge: bool):
        for key, value in data.items():
            full_key = prefix + key if prefix else key
            if isinstance(value, dict):
                child = section._children.get(key)
                if child is None:
                    child = section.add_child(key)
                self._load_dict_recursive(child, value, "", merge)
            else:
                section._values[key] = value

    def load_yaml(self, filepath: str, merge: bool = True):
        """Load configuration from YAML file"""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install pyyaml")

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self.load_dict(data, merge=merge)
        self._sources.append(filepath)
        self._recompute_checksum()

    def load_json(self, filepath: str, merge: bool = True):
        """Load configuration from JSON file"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_dict(data, merge=merge)
        self._sources.append(filepath)
        self._recompute_checksum()

    def load_env(self, prefix: str = "APP_", overwrite: bool = False):
        """Load configuration from environment variables

        Environment variables like APP_DATABASE__HOST map to
        database.host (double underscore = nested separator).
        """
        self._env_prefix = prefix
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Strip prefix and convert __ to .
                config_key = key[len(prefix):].lower()
                config_key = config_key.replace("__", ".")
                if not self.get(config_key) or overwrite:
                    self.set(config_key, value)

    def load_cli(self, args: List[str] = None) -> List[str]:
        """Parse CLI arguments into config.

        Expects: --section.key=value format.
        Returns unrecognized args.
        """
        import argparse
        if args is None:
            args = sys.argv[1:]

        remaining = []
        for arg in args:
            if arg.startswith("--") and "=" in arg:
                parts = arg[2:].split("=", 1)
                self.set(parts[0], parts[1])
            else:
                remaining.append(arg)
        return remaining

    def reload(self):
        """Reload from all known sources"""
        for source in self._sources:
            if source.endswith(".yaml") or source.endswith(".yml"):
                self.load_yaml(source, merge=False)
            elif source.endswith(".json"):
                self.load_json(source, merge=False)
        self._recompute_checksum()

    def _recompute_checksum(self):
        flat = self.flatten(include_sensitive=True)
        raw = json.dumps(flat, sort_keys=True)
        self._checksum = hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def checksum(self) -> str:
        return self._checksum

    @property
    def sources(self) -> List[str]:
        return list(self._sources)

    def flatten(self, include_sensitive: bool = False) -> Dict:
        return self._root.flatten(include_sensitive=include_sensitive)

    def to_dict(self, include_sensitive: bool = False) -> dict:
        return self._root.to_dict(include_sensitive=include_sensitive)

    def validate(self) -> List[ValidationError]:
        return self._root.validate()

    def export_json(self, filepath: str, include_sensitive: bool = False):
        """Export config to JSON file"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(include_sensitive), f,
                      ensure_ascii=False, indent=2)

    def export_env(self, filepath: str):
        """Export config as shell environment variables"""
        flat = self.flatten()
        with open(filepath, "w", encoding="utf-8") as f:
            for key, value in sorted(flat.items()):
                safe_key = key.upper().replace(".", "_")
                f.write("export {}={}\n".format(safe_key,
                                                shlex_quote(str(value))))


class ConfigWatcher:
    """Watch a config file for changes and hot-reload"""

    def __init__(self, config: Config, filepath: str,
                 interval: float = 2.0):
        self.config = config
        self.filepath = filepath
        self.interval = interval
        self._running = False
        self._last_mtime = 0
        self._callbacks: List[Callable] = []

    def on_change(self, callback: Callable):
        """Register callback for config change"""
        self._callbacks.append(callback)

    def start(self):
        """Start watching (blocking)"""
        self._running = True
        while self._running:
            self._check()
            time.sleep(self.interval)

    async def start_async(self):
        """Start watching (async)"""
        self._running = True
        while self._running:
            self._check()
            await asyncio.sleep(self.interval)

    def _check(self):
        try:
            mtime = os.path.getmtime(self.filepath)
            if mtime != self._last_mtime:
                self._last_mtime = mtime
                self.config.reload()
                for cb in self._callbacks:
                    try:
                        cb(self.config)
                    except Exception:
                        pass
        except FileNotFoundError:
            pass

    def stop(self):
        self._running = False


# ── Built-in configuration schemas ────────────────────────────────

def create_default_config() -> Config:
    """Create application config with sensible defaults"""
    cfg = Config("minxg")

    # Server section
    server = cfg.section("server")
    server.add_field("host", "0.0.0.0", str, description="Bind address")
    server.add_field("port", 8080, int, validator=Validator.integer)
    server.add_field("workers", 4, int,
                     validator=lambda v: Validator.integer(v, min_val=1, max_val=32))
    server.add_field("debug", False, bool, validator=Validator.boolean)
    server.add_field("log_level", "INFO", str,
                     validator=lambda v: Validator.choice(v, ["DEBUG", "INFO", "WARNING", "ERROR"]))

    # Database section
    db = cfg.section("database")
    db.add_field("engine", "sqlite", str,
                 validator=lambda v: Validator.choice(v, ["sqlite", "postgresql", "mysql"]))
    db.add_field("host", "localhost", str)
    db.add_field("port", 5432, int, validator=lambda v: Validator.integer(v, min_val=1, max_val=65535))
    db.add_field("name", "minxg", str)
    db.add_field("user", "", str)
    db.add_field("password", "", str, sensitive=True)
    db.add_field("pool_size", 5, int, validator=lambda v: Validator.integer(v, min_val=1, max_val=50))

    # Cache section
    cache = cfg.section("cache")
    cache.add_field("enabled", True, bool, validator=Validator.boolean)
    cache.add_field("backend", "memory", str,
                    validator=lambda v: Validator.choice(v, ["memory", "redis", "disk"]))
    cache.add_field("ttl", 300, int, validator=lambda v: Validator.integer(v, min_val=0))
    cache.add_field("max_size", 1000, int, validator=lambda v: Validator.integer(v, min_val=1))

    # Auth section
    auth = cfg.section("auth")
    auth.add_field("enabled", True, bool, validator=Validator.boolean)
    auth.add_field("method", "token", str,
                   validator=lambda v: Validator.choice(v, ["token", "session", "oauth2"]))
    auth.add_field("token_expiry", 3600, int,
                   validator=lambda v: Validator.integer(v, min_val=60))
    auth.add_field("secret_key", secrets.token_hex(32), str, sensitive=True)

    # Queue section
    queue = cfg.section("queue")
    queue.add_field("backend", "memory", str,
                    validator=lambda v: Validator.choice(v, ["memory", "redis", "rabbitmq"]))
    queue.add_field("max_retries", 3, int, validator=lambda v: Validator.integer(v, min_val=0))
    queue.add_field("worker_count", 4, int, validator=lambda v: Validator.integer(v, min_val=1))

    # Logging section
    logging = cfg.section("logging")
    logging.add_field("level", "INFO", str,
                      validator=lambda v: Validator.choice(v, ["DEBUG", "INFO", "WARNING", "ERROR"]))
    logging.add_field("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s", str)
    logging.add_field("file", None, str)
    logging.add_field("max_size_mb", 100, int,
                      validator=lambda v: Validator.integer(v, min_val=1))
    logging.add_field("backup_count", 5, int,
                      validator=lambda v: Validator.integer(v, min_val=0))

    return cfg


def shlex_quote(s: str) -> str:
    """Quote string for shell"""
    if not s:
        return "''"
    if re.match(r'^[a-zA-Z0-9_@%+=:,./-]*$', s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"