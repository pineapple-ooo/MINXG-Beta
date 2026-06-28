"""gateway.config — single source of truth for Gateway startup options.

Goal
----
Every place that asks ``what host/port does the gateway bind?``, ``what
model does it proxy?`` or ``which channels are enabled?`` used to read a
hodgepodge of kwargs, env-vars, and inline dicts. That made the gateway
fragile: tweaking ``config/minxg.yaml`` often meant re-implementing the
same defaults in three files.

``GatewayConfig`` fixes that. It is the only object that knows how
``config/gateway.yaml`` (and the legacy ``config/minxg.yaml``) maps to
runtime settings. ``GatewayServer.__init__`` consumes one; CLI verbs
construct one; tests instantiate one with overrides.

Reference: ``/storage/emulated/0/文件/mmm/gateway/channel.py`` and
``manager.py`` inspired the "channel = adapter identity + enabled flag"
shape — but this implementation is **fresh and MINXG-native**; it does
NOT inherit any code or naming from that reference project.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_GATEWAY_HOST = "0.0.0.0"
DEFAULT_GATEWAY_PORT = 18080
DEFAULT_AI_PROVIDER = "openai"
DEFAULT_AI_MODEL = "MiniMax-M3"
DEFAULT_AI_BASE_URL = "https://api.iamhc.cn/v1"
DEFAULT_PY_WORKER_HOST = "127.0.0.1"
DEFAULT_PY_WORKER_PORT = 19001


@dataclass
class AIConfig:
    """AI backend the gateway proxies chat requests to."""

    provider: str = DEFAULT_AI_PROVIDER
    model: str = DEFAULT_AI_MODEL
    base_url: str = DEFAULT_AI_BASE_URL
    api_key: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIConfig":
        if not isinstance(data, dict):
            data = {}
        return cls(
            provider=str(data.get("provider", DEFAULT_AI_PROVIDER)),
            model=str(data.get("model", DEFAULT_AI_MODEL)),
            base_url=str(data.get("base_url", DEFAULT_AI_BASE_URL)),
            api_key=str(data.get("api_key", "") or os.getenv("AI_API_KEY", "") or ""),
        )


@dataclass
class WorkerURL:
    """Where the Python worker pool listens for tool execution."""

    host: str = DEFAULT_PY_WORKER_HOST
    port: int = DEFAULT_PY_WORKER_PORT

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerURL":
        if not isinstance(data, dict):
            data = {}
        return cls(
            host=str(data.get("host", DEFAULT_PY_WORKER_HOST)),
            port=int(data.get("port", DEFAULT_PY_WORKER_PORT)),
        )


@dataclass
class GatewayBinding:
    """Socket the OpenAI-compatible gateway binds to."""

    host: str = DEFAULT_GATEWAY_HOST
    port: int = DEFAULT_GATEWAY_PORT

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayBinding":
        if not isinstance(data, dict):
            data = {}
        return cls(
            host=str(data.get("host", DEFAULT_GATEWAY_HOST)),
            port=int(data.get("port", DEFAULT_GATEWAY_PORT)),
        )


@dataclass
class ChannelConfig:
    """One inbound *"channel"* the gateway routes messages through.

    Inspired by the channel/manager pattern in
    ``/storage/emulated/0/文件/mmm/gateway`` but rewritten here as a
    plain dataclass — there is no inheritance from that project.
    """

    name: str
    enabled: bool = False
    adapter: str = "memory"          # adapter id used by ChannelManager
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelConfig":
        if not isinstance(data, dict):
            data = {}
        return cls(
            name=str(data.get("name", "default")),
            enabled=bool(data.get("enabled", False)),
            adapter=str(data.get("adapter", "memory")),
            options=dict(data.get("options", {}) or {}),
        )


@dataclass
class GatewayConfig:
    """Single config object every gateway-related call consumes.

    Construction order (highest priority last):

    1. Built-in defaults encoded in this module.
    2. Loaded YAML file (``config/gateway.yaml`` or a path you pass).
    3. ``MINXG_*`` environment variables.
    4. ``overrides`` argument to :py:meth:`from_sources`.
    """

    gateway: GatewayBinding = field(default_factory=GatewayBinding)
    ai: AIConfig = field(default_factory=AIConfig)
    workers: WorkerURL = field(default_factory=WorkerURL)
    channels: List[ChannelConfig] = field(default_factory=list)
    legacy: Dict[str, Any] = field(default_factory=dict)
    auth_token: str = ""
    schema_cache_ttl: float = 60.0

    # ----- factories --------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayConfig":
        data = data or {}
        gw = GatewayBinding.from_dict(data.get("gateway", {}))
        ai = AIConfig.from_dict(data.get("ai", {}))
        wk = WorkerURL.from_dict(data.get("workers", {}))
        channels_raw = data.get("channels", []) or []
        channels = [ChannelConfig.from_dict(c) for c in channels_raw]
        legacy = dict(data.get("legacy", {}) or {})
        auth_token = str(data.get("auth_token", "") or os.getenv("MINXG_GATEWAY_TOKEN", ""))
        ttl = float(data.get("schema_cache_ttl", 60.0))
        return cls(
            gateway=gw,
            ai=ai,
            workers=wk,
            channels=channels,
            legacy=legacy,
            auth_token=auth_token or secrets.token_hex(16),
            schema_cache_ttl=ttl,
        )

    @classmethod
    def from_sources(
        cls,
        project_root: Optional[Path] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> "GatewayConfig":
        """Build one config by reading ``config/gateway.yaml`` then layering overrides/env."""
        import yaml  # local: cheap import that may not exist in some test contexts

        root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
        primary = root / "config" / "gateway.yaml"
        legacy_path = root / "config" / "minxg.yaml"
        merged: Dict[str, Any] = {}
        for candidate in (primary, legacy_path):
            if candidate.exists():
                try:
                    payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                except Exception:
                    payload = {}
                if isinstance(payload, dict):
                    _deep_merge(merged, payload)
        if overrides:
            _deep_merge(merged, overrides)
        cfg = cls.from_dict(merged)
        # Environment overrides win last.
        cfg.gateway.host = os.getenv("MINXG_GATEWAY_HOST", cfg.gateway.host)
        cfg.gateway.port = int(os.getenv("MINXG_GATEWAY_PORT", str(cfg.gateway.port)))
        if os.getenv("AI_API_KEY"):
            cfg.ai.api_key = os.environ["AI_API_KEY"]
        if not cfg.channels:
            cfg.channels = [
                ChannelConfig(name="default", enabled=True, adapter="memory"),
            ]
        return cfg

    # ----- accessors --------------------------------------------------

    @property
    def py_worker_url(self) -> str:
        return self.workers.url

    def channel(self, name: str) -> Optional[ChannelConfig]:
        for ch in self.channels:
            if ch.name == name:
                return ch
        return None

    def channel_enabled(self, name: str) -> bool:
        ch = self.channel(name)
        return bool(ch and ch.enabled)


def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """Recursive ``dict.update`` — non-dict leaves are overwritten."""
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


__all__ = [
    "GatewayConfig",
    "GatewayBinding",
    "AIConfig",
    "WorkerURL",
    "ChannelConfig",
]
