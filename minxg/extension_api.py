"""
minxg/extension_api.py — v0.18.3 unified extension surface.

Three bridges:
  1. Plugin schema    — Python decorator-based plugin registry (like hermes-agent plugins/)
  2. MCP bridge        — wrap a registered tool as an MCP server method (stdio/SSE)
  3. ACP adapter       — Agent Communication Protocol client (hermes-agent native)

Extension layout mirrors hermes-agent's:
  - ``plugins/`` → per-domain Python packages with ``register_plugin()``
  - ``optional-mcps/`` → third-party MCP servers declared in config
  - ``acp_registry/`` → ACP peer endpoints

Single entry point: ``ExtensionRegistry.discover()`` scans all three
directories and builds a unified tool service list that the gateway
can stream to any AI model via OpenAI-compatible tool definitions.
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

log = logging.getLogger("minxg.extensions")

# ── Plugin schema ───────────────────────────────────────────────


@dataclass
class PluginManifest:
    """Self-reported metadata every plugin must provide."""
    name: str
    version: str
    description: str
    author: str = "MINXG community"
    requires_python: str = ">=3.8"
    minxg_min_version: str = "0.18.0"
    entrypoint: str = ""         # dotted module path of register() fn
    toolsets: List[str] = field(default_factory=list)  # e.g. ["file", "web", "terminal"]
    env_vars: Dict[str, str] = field(default_factory=dict)
    category: str = "general"


class PluginRegistry:
    """Central scaffold: plugins self-register here and tools are auto-discovered."""

    def __init__(self):
        self._plugins: Dict[str, PluginManifest] = {}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, manifest: PluginManifest) -> bool:
        with self._lock:
            if manifest.name in self._plugins:
                log.warning("Plugin %r already registered — skipped", manifest.name)
                return False
            self._plugins[manifest.name] = manifest
            log.info("Plugin registered: %s v%s (%s)", manifest.name, manifest.version, manifest.description)
        return True

    def add_tool(
        self,
        plugin_name: str,
        tool_name: str,
        schema: Dict[str, Any],
        handler: Callable,
        is_async: bool = True,
        requires_env: Optional[str] = None,
    ):
        qualified = f"{plugin_name}:{tool_name}"
        with self._lock:
            self._tools[qualified] = {
                "plugin": plugin_name, "tool": tool_name,
                "schema": schema, "handler": handler,
                "is_async": is_async, "requires_env": requires_env,
            }

    def list_tools(self, toolsets: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible tool definitions."""
        out = []
        for qname, tdef in self._tools.items():
            if toolsets and tdef["plugin"] not in toolsets:
                continue
            fn_def = tdef["schema"].get("function", tdef["schema"])
            out.append({
                "type": "function",
                "function": {
                    "name": qname,
                    "description": fn_def.get("description", ""),
                    "parameters": fn_def.get("parameters", fn_def.get("properties", {})),
                },
                "meta": {
                    "plugin": tdef["plugin"],
                    "is_async": tdef["is_async"],
                    "requires_env": tdef["requires_env"],
                },
            })
        return out

    def get_handler(self, qualified_name: str) -> Optional[Callable]:
        return self._tools.get(qualified_name, {}).get("handler")

    def statistics(self) -> Dict[str, Any]:
        return {
            "plugins_registered": len(self._plugins),
            "tools_registered": len(self._tools),
            "plugins": sorted(self._plugins.keys()),
        }


_PLUGIN_REGISTRY = PluginRegistry()


def register_plugin(manifest: PluginManifest) -> PluginManifest:
    """Decorator / imperative: register a plugin manifest."""
    _PLUGIN_REGISTRY.register(manifest)
    return manifest


# ── MCP bridge ───────────────────────────────────────────────────


@dataclass
class MCPEndpoint:
    """Declared MCP server endpoint (stdio or SSE/HTTP)."""
    name: str
    transport: str              # "stdio" | "sse"
    command: Optional[List[str]] = None  # for stdio
    url: Optional[str] = None           # for SSE
    env: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    auto_start: bool = False


class MCPBridge:
    """Bridge MINXG's tool registry to external MCP servers.

    For each MCP endpoint, discovers tools via ``tools/list`` and
    registers proxy handlers that forward calls to the MCP server.
    """

    def __init__(self):
        self._endpoints: Dict[str, MCPEndpoint] = {}
        self._proxied_tools: Dict[str, Dict[str, Any]] = {}

    def add_endpoint(self, ep: MCPEndpoint):
        self._endpoints[ep.name] = ep

    async def discover_tools(self, endpoint_name: str) -> List[Dict[str, Any]]:
        ep = self._endpoints.get(endpoint_name)
        if not ep:
            return []
        # MCP JSON-RPC handshake: initialize → tools/list
        tools = await self._mcp_list_tools(ep)
        for tdef in tools:
            qname = f"mcp:{endpoint_name}:{tdef['name']}"
            self._proxied_tools[qname] = {
                "endpoint": endpoint_name,
                "mcp_tool": tdef["name"],
                "schema": tdef,
            }
            # Register in the plugin registry so the gateway picks it up
            _PLUGIN_REGISTRY.add_tool(
                plugin_name=endpoint_name,
                tool_name=tdef["name"],
                schema=tdef,
                handler=self._make_proxy(ep, tdef["name"]),
                is_async=True,
            )
        return tools

    async def _mcp_list_tools(self, ep: MCPEndpoint) -> List[Dict[str, Any]]:
        """Stub — real impl ships in v0.19.0 with aiohttp/stdio."""
        return []

    def _make_proxy(self, ep: MCPEndpoint, tool_name: str) -> Callable:
        async def proxy(**kwargs):
            return {"status": "ok", "mcp_bridge": True,
                    "endpoint": ep.name, "tool": tool_name,
                    "note": "MCP bridge stub — v0.19.0 implements full JSON-RPC"}
        return proxy


_MCP_BRIDGE = MCPBridge()


# ── ACP adapter (Agent Communication Protocol) ──────────────────


class ACPAdapter:
    """Agent Communication Protocol client.

    Hermes-agent's ACP is a gRPC-based inter-agent protocol.
    MINXG's adapter connects to a running hermes-agent instance
    and exposes its tool surface as MINXG-native tools.
    """

    def __init__(self):
        self._peers: Dict[str, Dict[str, Any]] = {}
        self._connected = False

    def connect(self, endpoint: str = "localhost:50051",
                token: Optional[str] = None) -> bool:
        """Register an ACP peer endpoint."""
        self._peers["hermes-agent"] = {
            "endpoint": endpoint,
            "token": token,
            "status": "registered",
        }
        return True

    async def list_agent_tools(self, peer_name: str = "hermes-agent") -> List[Dict[str, Any]]:
        """ACP stub — real gRPC in v0.19.0."""
        return [{
            "name": "acp:delegate_to_hermes",
            "description": "Forward a task to hermes-agent via ACP (stub — v0.19.0)",
            "parameters": {"type": "object", "properties": {
                "task": {"type": "string", "description": "What to delegate"}
            }},
        }]


_ACP_ADAPTER = ACPAdapter()


# ── Unified discovery ───────────────────────────────────────────


class ExtensionRegistry:
    """Scan plugins/ + optional-mcps/ + acp_registry/ and build one tool surface."""

    def __init__(self):
        self._scanned = False
        self._plugin_dirs: List[Path] = []

    def discover(self, root: Optional[Path] = None) -> Dict[str, Any]:
        if root is None:
            root = Path(__file__).resolve().parent.parent  # repo root

        result = {
            "plugins_found": 0,
            "mcp_endpoints": 0,
            "acp_peers": 0,
            "total_tools": 0,
            "errors": [],
        }

        # 1. Scan plugins/
        plugin_dir = root / "plugins"
        if plugin_dir.is_dir():
            for pkg in plugin_dir.iterdir():
                if pkg.name.startswith("_") or pkg.name.startswith("."):
                    continue
                manifest_path = pkg / "MANIFEST.yaml" if (pkg / "MANIFEST.yaml").exists() else None
                if manifest_path:
                    try:
                        import yaml
                        with open(manifest_path) as f:
                            data = yaml.safe_load(f)
                        manifest = PluginManifest(**data)
                        _PLUGIN_REGISTRY.register(manifest)
                        result["plugins_found"] += 1
                    except Exception as e:
                        result["errors"].append(f"{pkg.name}: {e}")

        # 2. Scan optional-mcps/
        mcp_dir = root / "optional-mcps"
        if mcp_dir.is_dir():
            for cfg in mcp_dir.glob("*.json"):
                try:
                    data = json.loads(cfg.read_text())
                    ep = MCPEndpoint(**data)
                    _MCP_BRIDGE.add_endpoint(ep)
                    result["mcp_endpoints"] += 1
                except Exception as e:
                    result["errors"].append(f"mcp:{cfg.name}: {e}")

        # 3. Scan acp_registry/
        acp_dir = root / "acp_registry"
        if acp_dir.is_dir():
            for cfg in acp_dir.glob("*.json"):
                try:
                    data = json.loads(cfg.read_text())
                    _ACP_ADAPTER.connect(data.get("endpoint", "localhost:50051"),
                                         data.get("token"))
                    result["acp_peers"] += 1
                except Exception as e:
                    result["errors"].append(f"acp:{cfg.name}: {e}")

        result["total_tools"] = len(_PLUGIN_REGISTRY._tools)
        self._scanned = True
        return result

    def get_visible_tools(self, toolsets: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return _PLUGIN_REGISTRY.list_tools(toolsets)

    def call_tool(self, qualified_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        handler = _PLUGIN_REGISTRY.get_handler(qualified_name)
        if handler is None:
            return {"status": "error",
                    "error": f"unknown tool: {qualified_name!r}",
                    "available_sample": list(_PLUGIN_REGISTRY._tools.keys())[:10]}
        import asyncio
        try:
            if inspect.iscoroutinefunction(handler):
                return asyncio.get_event_loop().run_until_complete(handler(**params))
            return handler(**params)
        except Exception as e:
            return {"status": "error", "error": f"{type(e).__name__}: {e}"}


_EXTENSION_REGISTRY = ExtensionRegistry()


# ── Convenience exports ─────────────────────────────────────────

def discover_extensions(root: Optional[Path] = None) -> Dict[str, Any]:
    return _EXTENSION_REGISTRY.discover(root)

def get_visible_tools(toolsets: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    return _EXTENSION_REGISTRY.get_visible_tools(toolsets)

__all__ = [
    "PluginManifest", "PluginRegistry", "register_plugin", "_PLUGIN_REGISTRY",
    "MCPEndpoint", "MCPBridge", "_MCP_BRIDGE",
    "ACPAdapter", "_ACP_ADAPTER",
    "ExtensionRegistry", "_EXTENSION_REGISTRY",
    "discover_extensions", "get_visible_tools",
]